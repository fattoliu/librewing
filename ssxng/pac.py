from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import AppConfig

DEFAULT_PROXY_DOMAINS = [
    "google.com", "googleapis.com", "gstatic.com", "youtube.com", "youtu.be",
    "github.com", "githubusercontent.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "openai.com", "chatgpt.com", "wikipedia.org",
]


def build_pac(config: AppConfig) -> str:
    domains = sorted(set(DEFAULT_PROXY_DOMAINS + [x.strip().lstrip(".") for x in config.custom_rules if x.strip()]))
    tests = " ||\n        ".join(
        f'dnsDomainIs(host, "{d}") || shExpMatch(host, "*.{d}")' for d in domains
    ) or "false"
    port = config.profile.local_port
    return f'''function FindProxyForURL(url, host) {{
    host = host.toLowerCase();
    if (isPlainHostName(host) ||
        shExpMatch(host, "localhost") ||
        isInNet(dnsResolve(host), "10.0.0.0", "255.0.0.0") ||
        isInNet(dnsResolve(host), "172.16.0.0", "255.240.0.0") ||
        isInNet(dnsResolve(host), "192.168.0.0", "255.255.0.0")) {{
        return "DIRECT";
    }}
    if ({tests}) {{
        return "SOCKS5 127.0.0.1:{port}; SOCKS 127.0.0.1:{port}";
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
                self.send_header("Cache-Control", "no-cache")
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
