from __future__ import annotations

import subprocess
import time

from .config import LOG_FILE, AppConfig
from .core import HttpProxyCore, ShadowsocksCore, SystemProxy, _open_log, port_available


class NgShadowsocksCore(ShadowsocksCore):
    """ss-local launcher honoring the NG Advanced preference fields."""

    def start(self) -> None:
        if self.running():
            return
        profile = self.config.profile
        if not profile.server or not profile.password:
            raise RuntimeError("Please configure a Shadowsocks server first.")
        host = self.config.socks_listen_address or "127.0.0.1"
        if not port_available(profile.local_port, host):
            raise RuntimeError(f"Local SOCKS port {host}:{profile.local_port} is already in use.")
        runtime = self.config.write_runtime()
        self.log_handle = _open_log("ss-local")
        command = [self.find_ss_local(), "-c", str(runtime)]
        if self.config.verbose_mode:
            command.append("-v")
        self.process = subprocess.Popen(
            command,
            stdout=self.log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        time.sleep(0.2)
        if self.process.poll() is not None:
            code = self.process.returncode
            self.process = None
            self._close_log()
            raise RuntimeError(f"ss-local exited immediately with code {code}. Check {LOG_FILE} for details.")


class NgHttpProxyCore(HttpProxyCore):
    """HTTP bridge with an NG-compatible configurable listen address.

    The original bridge implementation is intentionally local-only. For safety,
    non-loopback binding is accepted by preferences but currently rejected here
    instead of accidentally exposing an unauthenticated proxy to the LAN.
    """

    def start(self) -> None:
        address = (self.config.http_listen_address or "127.0.0.1").strip()
        if address not in ("127.0.0.1", "localhost", "::1"):
            raise RuntimeError("HTTP proxy listen address must be localhost on Linux.")
        super().start()


class NgSystemProxy(SystemProxy):
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
