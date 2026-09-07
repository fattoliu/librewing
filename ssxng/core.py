from __future__ import annotations

import ipaddress
import os
import select
import shutil
import signal
import socket
import socketserver
import struct
import subprocess
import threading
import time
from typing import TextIO
from urllib.parse import urlsplit

from .config import AppConfig, LOG_FILE


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=check)


def port_available(port: int, host: str = "127.0.0.1") -> bool:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def connect_host(value: str) -> str:
    """Return a concrete local address suitable for connecting to a listener."""
    value = (value or "127.0.0.1").strip()
    if value == "0.0.0.0" or value == "localhost":
        return "127.0.0.1"
    if value == "::":
        return "::1"
    return value


def is_loopback_address(value: str) -> bool:
    """Return whether a configured listener is restricted to this machine."""
    value = (value or "127.0.0.1").strip().strip("[]")
    if value.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def require_safe_bind(value: str, allow_lan: bool, service: str) -> str:
    """Reject accidental unauthenticated LAN proxy exposure."""
    host = (value or "127.0.0.1").strip()
    if not allow_lan and not is_loopback_address(host):
        raise RuntimeError(
            f"{service} cannot listen on non-loopback address {host!r} unless LAN access is explicitly enabled."
        )
    return host


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
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(LOG_FILE.parent, 0o700)
    descriptor = os.open(LOG_FILE, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    os.fchmod(descriptor, 0o600)
    handle = os.fdopen(descriptor, "a", encoding="utf-8", buffering=1)
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
        host = require_safe_bind(
            self.config.socks_listen_address,
            self.config.socks_allow_lan,
            "SOCKS5 proxy",
        )
        if not port_available(profile.local_port, host):
            raise RuntimeError(
                f"Local SOCKS port {host}:{profile.local_port} is already in use.\n\n"
                "If you previously enabled shadowsocks-libev as a systemd service, stop it before using this client:\n"
                "sudo systemctl disable --now shadowsocks-libev-local@config.service"
            )
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


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise OSError("unexpected EOF")
        data.extend(chunk)
    return bytes(data)


def _socks5_connect(proxy_host: str, proxy_port: int, target_host: str, target_port: int) -> socket.socket:
    sock = socket.create_connection((proxy_host, int(proxy_port)), timeout=15)
    sock.settimeout(15)
    try:
        sock.sendall(b"\x05\x01\x00")
        if _recv_exact(sock, 2) != b"\x05\x00":
            raise OSError("SOCKS5 proxy rejected no-authentication method")

        try:
            ip = ipaddress.ip_address(target_host.strip("[]"))
        except ValueError:
            encoded = target_host.encode("idna")
            if len(encoded) > 255:
                raise OSError("target hostname is too long")
            address = b"\x03" + bytes([len(encoded)]) + encoded
        else:
            if ip.version == 4:
                address = b"\x01" + ip.packed
            else:
                address = b"\x04" + ip.packed

        sock.sendall(b"\x05\x01\x00" + address + struct.pack("!H", int(target_port)))
        head = _recv_exact(sock, 4)
        if head[0] != 5 or head[1] != 0:
            raise OSError(f"SOCKS5 CONNECT failed with reply code {head[1]}")
        atyp = head[3]
        if atyp == 1:
            _recv_exact(sock, 4)
        elif atyp == 4:
            _recv_exact(sock, 16)
        elif atyp == 3:
            _recv_exact(sock, _recv_exact(sock, 1)[0])
        else:
            raise OSError("invalid SOCKS5 address type")
        _recv_exact(sock, 2)
        sock.settimeout(None)
        return sock
    except Exception:
        sock.close()
        raise


def _relay(left: socket.socket, right: socket.socket) -> None:
    sockets = [left, right]
    while True:
        readable, _, _ = select.select(sockets, [], [], 60)
        if not readable:
            continue
        for source in readable:
            try:
                data = source.recv(65536)
            except OSError:
                return
            if not data:
                return
            target = right if source is left else left
            try:
                target.sendall(data)
            except OSError:
                return


def _split_host_port(value: str, default_port: int) -> tuple[str, int]:
    value = value.strip()
    if value.startswith("["):
        end = value.find("]")
        if end < 0:
            raise ValueError("invalid IPv6 host")
        host = value[1:end]
        rest = value[end + 1 :]
        return host, int(rest[1:]) if rest.startswith(":") else default_port
    if value.count(":") == 1:
        host, port = value.rsplit(":", 1)
        return host, int(port)
    return value, default_port


class _ThreadingHTTPProxy(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class _ThreadingHTTPProxy6(_ThreadingHTTPProxy):
    address_family = socket.AF_INET6


class HttpProxyCore:
    """Small HTTP/HTTPS proxy that tunnels traffic through the local SOCKS5 listener.

    This replaces the old Privoxy dependency. HTTPS uses CONNECT; plain HTTP
    absolute-form requests are rewritten to origin-form before being sent over
    SOCKS5. The bridge is intentionally local-only and requires no root access.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.server: _ThreadingHTTPProxy | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.running() or not self.config.http_enabled:
            return
        listen_host = require_safe_bind(
            self.config.http_listen_address,
            self.config.http_allow_lan,
            "HTTP proxy",
        )
        if not port_available(self.config.http_port, listen_host):
            raise RuntimeError(
                f"Local HTTP proxy port {listen_host}:{self.config.http_port} is already in use."
            )

        config = self.config
        socks_host = connect_host(config.socks_listen_address)

        class Handler(socketserver.BaseRequestHandler):
            def error_response(self, status: bytes) -> None:
                self.request.sendall(
                    b"HTTP/1.1 " + status + b"\r\n"
                    b"Proxy-Agent: LibreWing\r\n"
                    b"Connection: close\r\n\r\n"
                )

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
                        self.error_response(b"431 Request Header Fields Too Large")
                        return

                header_end = data.index(b"\r\n\r\n") + 4
                header = bytes(data[:header_end])
                body_prefix = bytes(data[header_end:])
                lines = header.decode("iso-8859-1").split("\r\n")
                try:
                    method, target, version = lines[0].split(" ", 2)
                except ValueError:
                    self.error_response(b"400 Bad Request")
                    return

                try:
                    if method.upper() == "CONNECT":
                        host, port = _split_host_port(target, 443)
                        remote = _socks5_connect(socks_host, config.profile.local_port, host, port)
                        try:
                            client.sendall(b"HTTP/1.1 200 Connection Established\r\nProxy-Agent: LibreWing\r\n\r\n")
                            if body_prefix:
                                remote.sendall(body_prefix)
                            client.settimeout(None)
                            _relay(client, remote)
                        finally:
                            remote.close()
                        return

                    parsed = urlsplit(target)
                    if parsed.scheme and parsed.scheme.lower() != "http":
                        raise ValueError("plain proxy requests must use the http scheme")
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
                    clean_headers = []
                    for line in lines[1:]:
                        lower = line.lower()
                        if not line or lower.startswith(
                            ("proxy-connection:", "proxy-authorization:", "connection:", "keep-alive:")
                        ):
                            continue
                        clean_headers.append(line)
                    clean_headers.append("Connection: close")
                    forwarded = (
                        f"{method} {path} {version}\r\n"
                        + "\r\n".join(clean_headers)
                        + "\r\n\r\n"
                    ).encode("iso-8859-1") + body_prefix

                    remote = _socks5_connect(socks_host, config.profile.local_port, host, int(port))
                    try:
                        remote.sendall(forwarded)
                        client.settimeout(None)
                        _relay(client, remote)
                    finally:
                        remote.close()
                except Exception:
                    try:
                        self.error_response(b"502 Bad Gateway")
                    except OSError:
                        pass

        try:
            server_class = _ThreadingHTTPProxy6 if ":" in listen_host else _ThreadingHTTPProxy
            self.server = server_class((listen_host, self.config.http_port), Handler)
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

    def _auto_mode(self, path: str) -> None:
        url = f"http://127.0.0.1:{self.config.pac_port}/{path}"
        self._gsettings("org.gnome.system.proxy", "autoconfig-url", f"'{url}'")
        self._gsettings("org.gnome.system.proxy", "mode", "'auto'")

    def global_mode(self) -> None:
        # Firefox can interpret GNOME's bare SOCKS setting as SOCKS4 even when
        # the local Shadowsocks listener is SOCKS5. Use PAC and state SOCKS5
        # explicitly so GNOME-aware browsers receive an unambiguous proxy type.
        self._auto_mode("global.pac")
        self.config.mode = "global"
        self.config.save()

    def pac_mode(self) -> None:
        self._auto_mode("proxy.pac")
        self.config.mode = "pac"
        self.config.save()
