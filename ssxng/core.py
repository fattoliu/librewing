from __future__ import annotations

import os
import shutil
import signal
import subprocess
from pathlib import Path

from .config import AppConfig


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=check)


class ShadowsocksCore:
    def __init__(self, config: AppConfig):
        self.config = config
        self.process: subprocess.Popen[str] | None = None

    def find_ss_local(self) -> str:
        path = shutil.which("ss-local")
        if not path:
            raise RuntimeError("ss-local not found. Install shadowsocks-libev first.")
        return path

    def start(self) -> None:
        if self.process and self.process.poll() is None:
            return
        profile = self.config.profile
        if not profile.server or not profile.password:
            raise RuntimeError("Please configure a Shadowsocks server first.")
        runtime = self.config.write_runtime()
        self.process = subprocess.Popen(
            [self.find_ss_local(), "-c", str(runtime)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
        )

    def stop(self) -> None:
        if not self.process or self.process.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            self.process.wait(timeout=3)
        except Exception:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except Exception:
                pass
        self.process = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def running(self) -> bool:
        return bool(self.process and self.process.poll() is None)


class SystemProxy:
    def __init__(self, config: AppConfig):
        self.config = config

    @staticmethod
    def _gsettings(schema: str, key: str, value: str) -> None:
        subprocess.run(["gsettings", "set", schema, key, value], check=True)

    def off(self) -> None:
        self._gsettings("org.gnome.system.proxy", "mode", "'none'")
        self.config.mode = "off"
        self.config.save()

    def manual(self) -> None:
        # Manual mode deliberately leaves GNOME system proxy disabled.
        self.off()
        self.config.mode = "manual"
        self.config.save()

    def global_mode(self) -> None:
        p = self.config.profile
        self._gsettings("org.gnome.system.proxy", "mode", "'manual'")
        self._gsettings("org.gnome.system.proxy", "use-same-proxy", "false")
        self._gsettings("org.gnome.system.proxy.socks", "host", "'127.0.0.1'")
        self._gsettings("org.gnome.system.proxy.socks", "port", str(p.local_port))
        self.config.mode = "global"
        self.config.save()

    def pac_mode(self) -> None:
        url = f"http://127.0.0.1:{self.config.pac_port}/proxy.pac"
        self._gsettings("org.gnome.system.proxy", "autoconfig-url", f"'{url}'")
        self._gsettings("org.gnome.system.proxy", "mode", "'auto'")
        self.config.mode = "pac"
        self.config.save()
