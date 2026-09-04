import socket
import struct
import threading

import pytest

from ssxng.config import AppConfig, ServerProfile
from ssxng.core import HttpProxyCore, require_safe_bind


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise OSError("unexpected EOF")
        data.extend(chunk)
    return bytes(data)


def _recv_until(sock: socket.socket, marker: bytes) -> bytes:
    data = bytearray()
    while marker not in data:
        chunk = sock.recv(65536)
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def _unused_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


class FakeSocks5:
    def __init__(self, *, tunnel: bool = False):
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.listener.settimeout(3)
        self.port = self.listener.getsockname()[1]
        self.tunnel = tunnel
        self.target: tuple[str, int] | None = None
        self.payload = b""
        self.error: Exception | None = None
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        try:
            connection, _address = self.listener.accept()
            with connection:
                assert _recv_exact(connection, 3) == b"\x05\x01\x00"
                connection.sendall(b"\x05\x00")
                head = _recv_exact(connection, 4)
                assert head[:3] == b"\x05\x01\x00"
                if head[3] == 1:
                    host = socket.inet_ntoa(_recv_exact(connection, 4))
                elif head[3] == 3:
                    host = _recv_exact(connection, _recv_exact(connection, 1)[0]).decode()
                else:
                    raise AssertionError(f"unexpected address type: {head[3]}")
                port = struct.unpack("!H", _recv_exact(connection, 2))[0]
                self.target = host, port
                connection.sendall(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
                if self.tunnel:
                    self.payload = _recv_exact(connection, 4)
                    connection.sendall(b"pong")
                else:
                    self.payload = _recv_until(connection, b"\r\n\r\n")
                    connection.sendall(
                        b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK"
                    )
        except Exception as exc:  # pragma: no cover - surfaced by finish()
            self.error = exc
        finally:
            self.listener.close()

    def finish(self) -> None:
        self.thread.join(timeout=3)
        assert not self.thread.is_alive()
        if self.error:
            raise self.error


def _config(socks_port: int) -> AppConfig:
    return AppConfig(
        http_port=_unused_port(),
        profiles=[ServerProfile(server="example.com", password="secret", local_port=socks_port)],
    )


def test_non_loopback_proxy_bind_requires_explicit_lan_opt_in():
    with pytest.raises(RuntimeError, match="LAN access is explicitly enabled"):
        require_safe_bind("0.0.0.0", False, "HTTP proxy")
    assert require_safe_bind("0.0.0.0", True, "HTTP proxy") == "0.0.0.0"
    assert require_safe_bind("::1", False, "HTTP proxy") == "::1"


def test_plain_http_request_is_rewritten_and_proxy_credentials_are_removed():
    socks = FakeSocks5()
    config = _config(socks.port)
    bridge = HttpProxyCore(config)
    bridge.start()
    try:
        with socket.create_connection(("127.0.0.1", config.http_port), timeout=2) as client:
            client.sendall(
                b"GET http://example.com:8080/path?q=1 HTTP/1.1\r\n"
                b"Host: example.com:8080\r\n"
                b"Proxy-Connection: keep-alive\r\n"
                b"Proxy-Authorization: Basic c2VjcmV0\r\n"
                b"Connection: keep-alive\r\n\r\n"
            )
            response = _recv_until(client, b"OK")
    finally:
        bridge.stop()
        socks.finish()

    assert response.endswith(b"OK")
    assert socks.target == ("example.com", 8080)
    assert socks.payload.startswith(b"GET /path?q=1 HTTP/1.1\r\n")
    assert b"Proxy-Connection:" not in socks.payload
    assert b"Proxy-Authorization:" not in socks.payload
    assert b"Connection: close\r\n" in socks.payload


def test_connect_establishes_a_bidirectional_socks5_tunnel():
    socks = FakeSocks5(tunnel=True)
    config = _config(socks.port)
    bridge = HttpProxyCore(config)
    bridge.start()
    try:
        with socket.create_connection(("127.0.0.1", config.http_port), timeout=2) as client:
            client.sendall(b"CONNECT secure.example:443 HTTP/1.1\r\nHost: secure.example\r\n\r\n")
            response = _recv_until(client, b"\r\n\r\n")
            assert response.startswith(b"HTTP/1.1 200 Connection Established")
            client.sendall(b"ping")
            assert _recv_exact(client, 4) == b"pong"
    finally:
        bridge.stop()
        socks.finish()

    assert socks.target == ("secure.example", 443)
    assert socks.payload == b"ping"

