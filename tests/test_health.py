from ssxng import health
from ssxng.config import AppConfig, ServerProfile


def test_health_reports_required_commands(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(health, "_port_free", lambda name, port: health.CheckResult(name, True, str(port)))
    cfg = AppConfig(profiles=[ServerProfile(server="example.com", password="x")])

    results = health.run_health_checks(cfg)

    names = {item.name for item in results}
    assert {"ss-local", "privoxy", "gsettings", "SOCKS port", "HTTP proxy port", "PAC port"} <= names
    assert all(item.ok for item in results)


def test_health_detects_identical_proxy_ports(monkeypatch):
    monkeypatch.setattr(health.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(health, "_port_free", lambda name, port: health.CheckResult(name, True, str(port)))
    cfg = AppConfig(pac_port=8090, http_port=8090, profiles=[ServerProfile(server="example.com", password="x")])

    results = health.run_health_checks(cfg)

    separation = next(item for item in results if item.name == "Proxy port separation")
    assert separation.ok is False


def test_format_health_report():
    report = health.format_health_report([
        health.CheckResult("A", True, "fine"),
        health.CheckResult("B", False, "missing"),
    ])
    assert "OK  A: fine" in report
    assert "FAIL  B: missing" in report
