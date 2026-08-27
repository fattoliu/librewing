import socket

from ssxng import health
from ssxng.config import AppConfig, ServerProfile


def test_health_reports_required_commands(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(health, "_socks_port", lambda name, port, host="127.0.0.1": health.CheckResult(name, True, f"{host}:{port}"))
    monkeypatch.setattr(health, "_service_port", lambda name, port, host="127.0.0.1": health.CheckResult(name, True, f"{host}:{port}"))
    cfg = AppConfig(profiles=[ServerProfile(server="example.com", password="x")])

    results = health.run_health_checks(cfg)

    names = {item.name for item in results}
    assert {"ss-local", "gsettings", "SOCKS port", "HTTP proxy port", "PAC port"} <= names
    assert "privoxy" not in names
    assert all(item.ok for item in results)


def test_health_reports_plugin(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(health, "_socks_port", lambda name, port, host="127.0.0.1": health.CheckResult(name, True, f"{host}:{port}"))
    monkeypatch.setattr(health, "_service_port", lambda name, port, host="127.0.0.1": health.CheckResult(name, True, f"{host}:{port}"))
    monkeypatch.setattr(health, "resolve_plugin", lambda plugin: "/usr/local/bin/obfs-local")
    cfg = AppConfig(profiles=[ServerProfile(server="example.com", password="x", plugin="obfs-local")])

    results = health.run_health_checks(cfg)

    plugin = next(item for item in results if item.name == "SIP003 plugin")
    assert plugin.ok is True
    assert plugin.detail == "/usr/local/bin/obfs-local"


def test_socks_port_accepts_running_socks5_listener(monkeypatch):
    monkeypatch.setattr(health, "_port_free", lambda name, port, host="127.0.0.1": health.CheckResult(name, False, "busy"))

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def settimeout(self, _timeout):
            pass

        def sendall(self, payload):
            assert payload == b"\x05\x01\x00"

        def recv(self, _size):
            return b"\x05\x00"

    monkeypatch.setattr(health.socket, "create_connection", lambda *_args, **_kwargs: FakeSocket())

    result = health._socks_port("SOCKS port", 1080)

    assert result.ok is True
    assert "SOCKS5" in result.detail


def test_socks_port_rejects_non_socks_listener(monkeypatch):
    monkeypatch.setattr(health, "_port_free", lambda name, port, host="127.0.0.1": health.CheckResult(name, False, "busy"))

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def settimeout(self, _timeout):
            pass

        def sendall(self, _payload):
            pass

        def recv(self, _size):
            return b"NO"

    monkeypatch.setattr(health.socket, "create_connection", lambda *_args, **_kwargs: FakeSocket())

    result = health._socks_port("SOCKS port", 1080)

    assert result.ok is False
    assert result.detail == "busy"


def test_service_port_accepts_running_listener(monkeypatch):
    monkeypatch.setattr(health, "_port_free", lambda name, port, host="127.0.0.1": health.CheckResult(name, False, "busy"))

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(health.socket, "create_connection", lambda *_args, **_kwargs: FakeConnection())

    result = health._service_port("HTTP proxy port", 1087)

    assert result.ok is True
    assert "listening" in result.detail


def test_format_health_report():
    report = health.format_health_report([
        health.CheckResult("A", True, "fine"),
        health.CheckResult("B", False, "missing"),
    ])
    assert "OK  A: fine" in report
    assert "FAIL  B: missing" in report
