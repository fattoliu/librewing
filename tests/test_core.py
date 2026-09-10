import socket

from ssxng.config import AppConfig
from ssxng.core import HttpProxyCore, _split_host_port, wait_for_listener


class _RunningProcess:
    @staticmethod
    def poll():
        return None


def test_wait_for_listener_detects_ready_socket():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    try:
        assert wait_for_listener("127.0.0.1", listener.getsockname()[1], _RunningProcess(), timeout=0.2)
    finally:
        listener.close()


def test_split_host_port_supports_ipv4_names_and_ipv6():
    assert _split_host_port("example.com:443", 80) == ("example.com", 443)
    assert _split_host_port("example.com", 80) == ("example.com", 80)
    assert _split_host_port("[::1]:8443", 80) == ("::1", 8443)


def test_http_proxy_core_lifecycle_uses_configured_port():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()

    config = AppConfig(http_port=port)
    bridge = HttpProxyCore(config)
    bridge.start()
    try:
        assert bridge.running()
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
    finally:
        bridge.stop()
    assert not bridge.running()
