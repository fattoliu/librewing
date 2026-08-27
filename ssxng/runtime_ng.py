from __future__ import annotations

import socket
import socketserver
import subprocess
import threading
import time
from urllib.parse import urlsplit

from .config import LOG_FILE
from .core import (
    ShadowsocksCore,
    SystemProxy,
    _open_log,
    _relay,
    _socks5_connect,
    _split_host_port,
    port_available,
)


def _connect_host(value: str) -> str:
    value = (value or "127.0.0.1").strip()
    if value == "0.0.0.0":
        return "127.0.0.1"
    if value == "::":
        return "::1"
    if value == "localhost":
        return "127.0.0.1"
    return value


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


class _ThreadingHTTPProxy(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class NgHttpProxyCore:
    """HTTP/HTTPS bridge with the listen address exposed by NG preferences."""

    def __init__(self, config):
        self.config = config
        self.server: _ThreadingHTTPProxy | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.running() or not self.config.http_enabled:
            return
        listen_host = (self.config.http_listen_address or "127.0.0.1").strip()
        if not port_available(self.config.http_port, listen_host):
            raise RuntimeError(
                f"Local HTTP proxy port {listen_host}:{self.config.http_port} is already in use."
            )

        config = self.config
        socks_host = _connect_host(config.socks_listen_address)

        class Handler(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                client: socket.socket = self.request
                client.settimeout(15)
                data = bytearray()
                while b"\r\n\r\n" not in data:
                    chunk = client.recv(65536)
                    if not chunk:
                        return
                    data.extend(chunk)
                    if len(data) > 1024 * 1024:
                        client.sendall(
                            b"HTTP/1.1 431 Request Header Fields Too Large\r\nConnection: close\r\n\r\n"
                        )
                        return

                header_end = data.index(b"\r\n\r\n") + 4
                header = bytes(data[:header_end])
                body_prefix = bytes(data[header_end:])
                lines = header.decode("iso-8859-1").split("\r\n")
                try:
                    method, target, version = lines[0].split(" ", 2)
                except ValueError:
                    client.sendall(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
                    return

                try:
                    if method.upper() == "CONNECT":
                        host, port = _split_host_port(target, 443)
                        remote = _socks5_connect(socks_host, config.profile.local_port, host, port)
                        try:
                            client.sendall(
                                b"HTTP/1.1 200 Connection Established\r\n"
                                b"Proxy-Agent: ShadowsocksX-NG-Linux\r\n\r\n"
                            )
                            if body_prefix:
                                remote.sendall(body_prefix)
                            client.settimeout(None)
                            _relay(client, remote)
                        finally:
                            remote.close()
                        return

                    parsed = urlsplit(target)
                    host_header = next(
                        (line[5:].strip() for line in lines[1:] if line.lower().startswith("host:")),
                        "",
                    )
                    host = parsed.hostname
                    port = parsed.port
                    if not host:
                        host, port = _split_host_port(host_header, 80)
                    else:
                        port = port or (443 if parsed.scheme == "https" else 80)
                    if not host:
                        raise ValueError("missing target host")

                    path = parsed.path or "/"
                    if parsed.query:
                        path += "?" + parsed.query
                    clean_headers = [
                        line
                        for line in lines[1:]
                        if line and not line.lower().startswith("proxy-connection:")
                    ]
                    forwarded = (
                        f"{method} {path} {version}\r\n"
                        + "\r\n".join(clean_headers)
                        + "\r\n\r\n"
                    ).encode("iso-8859-1") + body_prefix

                    remote = _socks5_connect(
                        socks_host, config.profile.local_port, host, int(port)
                    )
                    try:
                        remote.sendall(forwarded)
                        client.settimeout(None)
                        _relay(client, remote)
                    finally:
                        remote.close()
                except Exception:
                    try:
                        client.sendall(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
                    except OSError:
                        pass

        try:
            self.server = _ThreadingHTTPProxy((listen_host, self.config.http_port), Handler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
        except Exception:
            if self.server:
                self.server.server_close()
            self.server = None
            self.thread = None
            raise

    def stop(self) -> None:
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        self.server = None
        self.thread = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def running(self) -> bool:
        return bool(self.server and self.thread and self.thread.is_alive())


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
