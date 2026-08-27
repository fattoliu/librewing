from ssxng import health
from ssxng.config import AppConfig, ServerProfile


def test_health_reports_required_commands(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(health, "_port_free", lambda name, port: health.CheckResult(name, True, str(port)))
    cfg = AppConfig(profiles=[ServerProfile(server="example.com", password="x")])

    results = health.run_health_checks(cfg)

    names = {item.name for item in results}
    assert {"ss-local", "gsettings", "SOCKS port", "PAC port"} <= names
    assert "privoxy" not in names
    assert "HTTP proxy port" not in names
    assert all(item.ok for item in results)


def test_health_reports_plugin(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(health, "_port_free", lambda name, port: health.CheckResult(name, True, str(port)))
    monkeypatch.setattr(health, "resolve_plugin", lambda plugin: "/usr/local/bin/obfs-local")
    cfg = AppConfig(profiles=[ServerProfile(server="example.com", password="x", plugin="obfs-local")])

    results = health.run_health_checks(cfg)

    plugin = next(item for item in results if item.name == "SIP003 plugin")
    assert plugin.ok is True
    assert plugin.detail == "/usr/local/bin/obfs-local"


def test_format_health_report():
    report = health.format_health_report([
        health.CheckResult("A", True, "fine"),
        health.CheckResult("B", False, "missing"),
    ])
    assert "OK  A: fine" in report
    assert "FAIL  B: missing" in report
