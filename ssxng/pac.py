from __future__ import annotations

import base64
import json
import re
import shutil
import socket
import subprocess
import threading
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .config import ABP_TEMPLATE_FILE, AppConfig, GFWLIST_FILE

DOMAIN_RE = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$", re.I)


def _local_proxy_available(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.3):
            return True
    except OSError:
        return False


def _download(url: str, timeout: int = 20, socks_port: int | None = None) -> bytes:
    """Download rule assets with a resilient proxy/direct fallback path.

    Prefer the active local SOCKS tunnel, but a listening port does not
    guarantee that the upstream tunnel is healthy. curl exit 28 is a timeout;
    in that case fall back to urllib, which also honours the user's standard
    http_proxy/https_proxy environment when present.
    """
    curl = shutil.which("curl")
    socks_error: Exception | None = None
    if socks_port and curl and _local_proxy_available(socks_port):
        try:
            completed = subprocess.run(
                [
                    curl,
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--location",
                    "--connect-timeout",
                    "10",
                    "--max-time",
                    str(timeout),
                    "--retry",
                    "2",
                    "--retry-delay",
                    "1",
                    "--socks5-hostname",
                    f"127.0.0.1:{int(socks_port)}",
                    url,
                ],
                check=True,
                capture_output=True,
            )
            return completed.stdout
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            socks_error = exc

    request = urllib.request.Request(url, headers={"User-Agent": "ShadowsocksX-NG-Linux/0.2"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except Exception as direct_error:
        if socks_error is not None:
            raise RuntimeError(
                f"Download failed through local SOCKS and fallback connection: {direct_error}"
            ) from socks_error
        raise


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(data)
    temp.replace(path)


def decode_gfwlist(raw: bytes) -> str:
    compact = b"".join(raw.split())
    try:
        return base64.b64decode(compact + b"=" * (-len(compact) % 4)).decode("utf-8", "ignore")
    except Exception:
        return raw.decode("utf-8", "ignore")


def _domain_from_rule(rule: str) -> str | None:
    rule = rule.strip()
    if not rule or rule.startswith("!") or rule.startswith("[") or rule.startswith("@@"):
        return None
    rule = rule.lstrip("|")
    if rule.startswith("http://") or rule.startswith("https://"):
        rule = urlparse(rule).hostname or ""
    else:
        rule = rule.split("/")[0]
    rule = rule.lstrip(".").replace("^", "")
    if rule.startswith("*."):
        rule = rule[2:]
    if "*" in rule or not DOMAIN_RE.match(rule):
        return None
    return rule.lower()


def parse_gfwlist(raw: bytes) -> set[str]:
    domains: set[str] = set()
    for line in decode_gfwlist(raw).splitlines():
        domain = _domain_from_rule(line)
        if domain:
            domains.add(domain)
    return domains


def _user_rule_lines(config: AppConfig) -> list[str]:
    result: list[str] = []
    for line in config.custom_rules:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("!") or line.startswith("["):
            continue
        result.append(line)
    return result


def merged_abp_rules(config: AppConfig) -> list[str]:
    """Merge custom rules ahead of GFWList, matching ShadowsocksX-NG precedence."""
    user_rules = _user_rule_lines(config)
    upstream: list[str] = []
    if config.gfwlist_enabled and GFWLIST_FILE.exists():
        upstream = decode_gfwlist(GFWLIST_FILE.read_bytes()).splitlines()

    user_set = set(user_rules)
    merged = list(user_rules)
    for line in upstream:
        line = line.strip()
        if not line or line[0] in "![":
            continue
        index = 0
        while index < len(line) and line[index] in "@|":
            index += 1
        comparable = line if index == 0 else line[index:]
        if line in user_set or comparable in user_set:
            continue
        merged.append(line)
    return merged


def update_gfwlist(config: AppConfig, timeout: int = 20) -> int:
    socks_port = config.profile.local_port
    raw = _download(config.gfwlist_url, timeout=timeout, socks_port=socks_port)
    domains = parse_gfwlist(raw)
    if len(domains) < 100:
        raise ValueError("Downloaded GFWList does not contain enough valid rules")

    # Keep caching the upstream ShadowsocksX-NG template for compatibility and
    # future precise-rule work, although Linux serves a compact PAC at runtime.
    template = _download(config.abp_template_url, timeout=timeout, socks_port=socks_port)
    template_text = template.decode("utf-8", "strict")
    if "__RULES__" not in template_text or "function FindProxyForURL" not in template_text:
        raise ValueError("Downloaded ShadowsocksX-NG ABP template is invalid")

    _atomic_write(GFWLIST_FILE, raw)
    _atomic_write(ABP_TEMPLATE_FILE, template)
    config.gfwlist_updated_at = datetime.now(timezone.utc).isoformat()
    config.save()
    return len(domains)


def load_gfwlist_domains(config: AppConfig) -> set[str]:
    if not config.gfwlist_enabled or not GFWLIST_FILE.exists():
        return set()
    try:
        return parse_gfwlist(GFWLIST_FILE.read_bytes())
    except OSError:
        return set()


def _parse_custom_rules(rules: list[str]) -> tuple[set[str], set[str]]:
    proxy: set[str] = set()
    direct: set[str] = set()
    for value in rules:
        value = value.strip()
        if not value or value.startswith("#") or value.startswith("!"):
            continue
        target = direct if value.startswith("@@") else proxy
        if value.startswith("@@"):
            value = value[2:].strip()
        domain = _domain_from_rule(value)
        if domain:
            target.add(domain)
    return proxy, direct


def _domain_sets(config: AppConfig) -> tuple[set[str], set[str]]:
    """Extract fast domain rules while preserving whitelist precedence."""
    proxy: set[str] = set()
    direct: set[str] = set()
    for raw_rule in merged_abp_rules(config):
        rule = raw_rule.strip()
        if not rule:
            continue
        is_direct = rule.startswith("@@")
        if is_direct:
            rule = rule[2:].strip()
        domain = _domain_from_rule(rule)
        if not domain:
            continue
        (direct if is_direct else proxy).add(domain)
    return proxy, direct


def _socks5(config: AppConfig) -> str:
    return f"SOCKS5 127.0.0.1:{config.profile.local_port}"


def build_global_pac(config: AppConfig) -> str:
    proxy = _socks5(config)
    return f'''function FindProxyForURL(url, host) {{
    if (isPlainHostName(host) || shExpMatch(host, "localhost")) {{
        return "DIRECT";
    }}
    return "{proxy}; DIRECT";
}}
'''


def build_pac(config: AppConfig) -> str:
    """Build a compact cross-browser PAC from GFWList/custom domain rules."""
    proxy_domains, direct_domains = _domain_sets(config)
    proxy_json = json.dumps(sorted(proxy_domains), ensure_ascii=False, separators=(",", ":"))
    direct_json = json.dumps(sorted(direct_domains), ensure_ascii=False, separators=(",", ":"))
    proxy = _socks5(config)
    return f'''// ShadowsocksX-NG Linux compact PAC
var proxyDomains = {proxy_json};
var directDomains = {direct_json};

function contains(sorted, value) {{
    var lo = 0;
    var hi = sorted.length - 1;
    while (lo <= hi) {{
        var mid = (lo + hi) >> 1;
        var current = sorted[mid];
        if (current === value) return true;
        if (current < value) lo = mid + 1;
        else hi = mid - 1;
    }}
    return false;
}}

function domainMatches(sorted, host) {{
    while (host) {{
        if (contains(sorted, host)) return true;
        var dot = host.indexOf(".");
        if (dot < 0) break;
        host = host.substring(dot + 1);
    }}
    return false;
}}

function FindProxyForURL(url, host) {{
    host = (host || "").toLowerCase();
    if (!host || isPlainHostName(host) || host === "localhost") {{
        return "DIRECT";
    }}
    if (domainMatches(directDomains, host)) {{
        return "DIRECT";
    }}
    if (domainMatches(proxyDomains, host)) {{
        return "{proxy}; DIRECT";
    }}
    return "DIRECT";
}}
'''


class PacServer:
    def __init__(self, config: AppConfig):
        self.config = config
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.httpd:
            return
        config = self.config

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                path = urlparse(self.path).path
                if path in ("/", "/proxy.pac"):
                    payload = build_pac(config)
                elif path == "/global.pac":
                    payload = build_global_pac(config)
                else:
                    self.send_error(404)
                    return
                data = payload.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ns-proxy-autoconfig")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *_args) -> None:
                return

        self.httpd = ThreadingHTTPServer(("127.0.0.1", config.pac_port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if not self.httpd:
            return
        self.httpd.shutdown()
        self.httpd.server_close()
        self.httpd = None
        self.thread = None