from __future__ import annotations

import base64
import re
import threading
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import AppConfig, GFWLIST_FILE

DOMAIN_RE = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}$", re.I)


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
    compact = b"".join(raw.split())
    try:
        decoded = base64.b64decode(compact + b"=" * (-len(compact) % 4)).decode("utf-8", "ignore")
    except Exception:
        decoded = raw.decode("utf-8", "ignore")
    domains: set[str] = set()
    for line in decoded.splitlines():
        domain = _domain_from_rule(line)
        if domain:
            domains.add(domain)
    return domains


def update_gfwlist(config: AppConfig, timeout: int = 20) -> int:
    request = urllib.request.Request(config.gfwlist_url, headers={"User-Agent": "ShadowsocksX-NG-Linux/0.2"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    domains = parse_gfwlist(raw)
    if len(domains) < 100:
        raise ValueError("Downloaded GFWList does not contain enough valid rules")
    GFWLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    GFWLIST_FILE.write_bytes(raw)
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
        if not value or value.startswith("#"):
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


def build_pac(config: AppConfig) -> str:
    custom_proxy, custom_direct = _parse_custom_rules(config.custom_rules)
    proxy_domains = load_gfwlist_domains(config) | custom_proxy
    direct_tests = _domain_tests(custom_direct)
    proxy_tests = _domain_tests(proxy_domains)
    proxy = f"PROXY 127.0.0.1:{config.http_port}"
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
                if urlparse(self.path).path not in ("/", "/proxy.pac"):
                    self.send_error(404)
                    return
                data = build_pac(config).encode("utf-8")
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
