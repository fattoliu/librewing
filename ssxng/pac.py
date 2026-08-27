from __future__ import annotations

import base64
import json
import re
import threading
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .config import ABP_TEMPLATE_FILE, AppConfig, GFWLIST_FILE

DOMAIN_RE = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$", re.I)
UPSTREAM_PROXY_DECLARATION = (
    'var proxy = "SOCKS5 __SOCKS5ADDR__:__SOCKS5PORT__; '
    'SOCKS __SOCKS5ADDR__:__SOCKS5PORT__; DIRECT;";'
)


def _download(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ShadowsocksX-NG-Linux/0.2"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


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
    raw = _download(config.gfwlist_url, timeout=timeout)
    domains = parse_gfwlist(raw)
    if len(domains) < 100:
        raise ValueError("Downloaded GFWList does not contain enough valid rules")

    template = _download(config.abp_template_url, timeout=timeout)
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


def _domain_tests(domains: set[str]) -> str:
    if not domains:
        return "false"
    return " ||\n        ".join(
        f'dnsDomainIs(host, "{d}") || shExpMatch(host, "*.{d}")' for d in sorted(domains)
    )


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


def _build_fallback_pac(config: AppConfig) -> str:
    custom_proxy, custom_direct = _parse_custom_rules(config.custom_rules)
    proxy_domains = load_gfwlist_domains(config) | custom_proxy
    direct_tests = _domain_tests(custom_direct)
    proxy_tests = _domain_tests(proxy_domains)
    proxy = _socks5(config)
    return f'''function FindProxyForURL(url, host) {{
    host = host.toLowerCase();
    if (isPlainHostName(host) || shExpMatch(host, "localhost")) {{
        return "DIRECT";
    }}
    if ({direct_tests}) {{
        return "DIRECT";
    }}
    if ({proxy_tests}) {{
        return "{proxy}; DIRECT";
    }}
    return "DIRECT";
}}
'''


def build_pac(config: AppConfig) -> str:
    if not ABP_TEMPLATE_FILE.exists():
        return _build_fallback_pac(config)

    try:
        template = ABP_TEMPLATE_FILE.read_text(encoding="utf-8")
        rules_json = json.dumps(merged_abp_rules(config), ensure_ascii=False, separators=(",", ":"))
        proxy_declaration = f'var proxy = "{_socks5(config)}; DIRECT;";'
        pac = template.replace("__RULES__", rules_json)
        pac = pac.replace(UPSTREAM_PROXY_DECLARATION, proxy_declaration)
        pac = pac.replace("__SOCKS5ADDR__", "127.0.0.1")
        pac = pac.replace("__SOCKS5PORT__", str(config.profile.local_port))
        return pac
    except (OSError, UnicodeError, ValueError):
        return _build_fallback_pac(config)


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
