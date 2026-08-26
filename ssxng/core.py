from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import TextIO

from .config import AppConfig, LOG_FILE, PRIVOXY_CONFIG_FILE


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=check)


def port_available(port: int, host: str = "127.0.0.1") -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if not process or process.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait(timeout=3)
    except Exception:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except Exception:
            pass


def _open_log(component: str) -> TextIO:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handle = LOG_FILE.open("a", encoding="utf-8", buffering=1)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    handle.write(f"\n[{stamp}] === {component} start ===\n")
    return handle


class ShadowsocksCore:
    def __init__(self, config: AppConfig):
        self.config = config
        self.process: subprocess.Popen[str] | None = None
        self.log_handle: TextIO | None = None

    def find_ss_local(self) -> str:
        path = shutil.which("ss-local")
        if not path:
            raise RuntimeError("ss-local not found. Install shadowsocks-libev first.")
        return path

    def start(self) -> None:
        if self.running():
            return
        profile = self.config.profile
        if not profile.server or not profile.password:
            raise RuntimeError("Please configure a Shadowsocks server first.")
        if not port_available(profile.local_port):
            raise RuntimeError(
                f"Local SOCKS port {profile.local_port} is already in use.\n\n"
                "If you previously enabled shadowsocks-libev as a systemd service, stop it before using this client:\n"
                "sudo systemctl disable --now shadowsocks-libev-local@config.service"
            )
        runtime = self.config.write_runtime()
        self.log_handle = _open_log("ss-local")
        self.process = subprocess.Popen(
            [self.find_ss_local(), "-c", str(runtime), "-v"],
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
            raise RuntimeError(
                f"ss-local exited immediately with code {code}. Check {LOG_FILE} for details."
            )

    def _close_log(self) -> None:
        if self.log_handle:
            self.log_handle.close()
            self.log_handle = None

    def stop(self) -> None:
        _stop_process(self.process)
        self.process = None
        self._close_log()

    def restart(self) -> None:
        self.stop()
        self.start()

    def running(self) -> bool:
        return bool(self.process and self.process.poll() is None)


class HttpProxyCore:
    """Runs a private Privoxy instance that forwards HTTP(S) to local SOCKS5."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.process: subprocess.Popen[str] | None = None
        self.log_handle: TextIO | None = None

    def find_privoxy(self) -> str:
        path = shutil.which("privoxy")
        if not path:
            raise RuntimeError("privoxy not found. Install the privoxy package first.")
        return path

    def write_config(self) -> Path:
        p = self.config.profile
        PRIVOXY_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        PRIVOXY_CONFIG_FILE.write_text(
            "\n".join(
                [
                    f"listen-address  127.0.0.1:{self.config.http_port}",
                    "toggle  1",
                    "enable-remote-toggle  0",
                    "enable-edit-actions  0",
                    "enforce-blocks  0",
                    "buffer-limit  4096",
                    "forwarded-connect-retries  2",
                    "accept-intercepted-requests  0",
                    "allow-cgi-request-crunching  0",
                    "split-large-forms  0",
                    "keep-alive-timeout  300",
                    "tolerate-pipelining  1",
                    "socket-timeout  300",
                    f"forward-socks5t / 127.0.0.1:{p.local_port} .",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return PRIVOXY_CONFIG_FILE

    def start(self) -> None:
        if self.running():
            return
        if not port_available(self.config.http_port):
            raise RuntimeError(f"Local HTTP proxy port {self.config.http_port} is already in use.")
        config = self.write_config()
        self.log_handle = _open_log("privoxy")
        self.process = subprocess.Popen(
            [self.find_privoxy(), "--no-daemon", str(config)],
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
            raise RuntimeError(
                f"Privoxy exited immediately with code {code}. Check {LOG_FILE} for details."
            )

    def _close_log(self) -> None:
        if self.log_handle:
            self.log_handle.close()
            self.log_handle = None

    def stop(self) -> None:
        _stop_process(self.process)
        self.process = None
        self._close_log()

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
        self.off()
        self.config.mode = "manual"
        self.config.save()

    def global_mode(self) -> None:
        port = self.config.http_port
        self._gsettings("org.gnome.system.proxy", "mode", "'manual'")
        self._gsettings("org.gnome.system.proxy", "use-same-proxy", "false")
        for schema in ("org.gnome.system.proxy.http", "org.gnome.system.proxy.https"):
            self._gsettings(schema, "host", "'127.0.0.1'")
            self._gsettings(schema, "port", str(port))
        self._gsettings("org.gnome.system.proxy.socks", "host", "'127.0.0.1'")
        self._gsettings("org.gnome.system.proxy.socks", "port", str(self.config.profile.local_port))
        self.config.mode = "global"
        self.config.save()

    def pac_mode(self) -> None:
        url = f"http://127.0.0.1:{self.config.pac_port}/proxy.pac"
        self._gsettings("org.gnome.system.proxy", "autoconfig-url", f"'{url}'")
        self._gsettings("org.gnome.system.proxy", "mode", "'auto'")
        self.config.mode = "pac"
        self.config.save()
