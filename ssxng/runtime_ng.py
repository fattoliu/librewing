from __future__ import annotations

import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import GFWLIST_FILE
from .core import (
    HttpProxyCore,
    ShadowsocksCore,
    SystemProxy,
)
from .pac import build_global_pac, build_pac, update_gfwlist


class NgShadowsocksCore(ShadowsocksCore):
    """Compatibility name for the advanced-aware core implementation."""


class NgHttpProxyCore(HttpProxyCore):
    """Compatibility name for the advanced-aware HTTP bridge."""


class NgPacServer:
    """PAC server honoring NG's localhost-only binding preference."""

    def __init__(self, config):
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
                self.send_header("X-ShadowsocksX-NG-Linux", "PAC")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *_args) -> None:
                return

        host = "127.0.0.1" if config.pac_bind_localhost else "0.0.0.0"
        self.httpd = ThreadingHTTPServer((host, config.pac_port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        if not self.httpd:
            return
        self.httpd.shutdown()
        self.httpd.server_close()
        self.httpd = None
        self.thread = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def running(self) -> bool:
        return bool(self.httpd and self.thread and self.thread.is_alive())


class NgSystemProxy(SystemProxy):
    def pac_mode(self) -> None:
        # A completely fresh install has no cached GFWList yet. Bootstrap it
        # through the already-running local SOCKS tunnel before enabling PAC,
        # so first-time users do not have to discover "Update GFWList" first.
        if not GFWLIST_FILE.exists() or GFWLIST_FILE.stat().st_size == 0:
            update_gfwlist(self.config, timeout=45)

        # GNOME/Chromium can cache PAC responses despite no-cache headers.
        # Key the URL to all generated PAC content, including custom rules.
        revision = hashlib.sha256(build_pac(self.config).encode()).hexdigest()[:16]
        url = f"http://127.0.0.1:{self.config.pac_port}/proxy.pac?v={revision}"
        self._gsettings("org.gnome.system.proxy", "autoconfig-url", repr(url))
        self._gsettings("org.gnome.system.proxy", "mode", "'auto'")
        self.config.mode = "pac"
        self.config.save()

    def external_pac_mode(self) -> None:
        url = self.config.external_pac_url.strip()
        if not url.startswith(("http://", "https://")):
            raise RuntimeError("Please configure a valid External PAC URL first.")
        self._gsettings("org.gnome.system.proxy", "autoconfig-url", repr(url))
        self._gsettings("org.gnome.system.proxy", "mode", "'auto'")
        self.config.mode = "external_pac"
        self.config.save()

    def apply_exceptions(self) -> None:
        values = [value.strip() for value in self.config.proxy_exceptions.split(",") if value.strip()]
        literal = "[" + ", ".join(repr(value) for value in values) + "]"
        try:
            self._gsettings("org.gnome.system.proxy", "ignore-hosts", literal)
        except Exception:
            pass
