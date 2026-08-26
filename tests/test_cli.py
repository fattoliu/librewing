from __future__ import annotations

from ssxng import cli
from ssxng.config import AppConfig, ServerProfile
from ssxng.health import CheckResult


def _config() -> AppConfig:
    return AppConfig(profiles=[ServerProfile(name="Demo", server="example.com", password="secret")])


def test_safe_profile_redacts_password():
    data = cli._safe_profile(_config())
    assert data["password"] == "***"
    assert data["server"] == "example.com"


def test_health_exit_code_success(monkeypatch, capsys):
    monkeypatch.setattr(cli.AppConfig, "load", classmethod(lambda cls: _config()))
    monkeypatch.setattr(cli, "run_health_checks", lambda _cfg: [CheckResult("x", True, "ok")])
    assert cli.main(["health"]) == 0
    out = capsys.readouterr().out
    assert "1 passed, 0 failed" in out


def test_health_exit_code_failure(monkeypatch, capsys):
    monkeypatch.setattr(cli.AppConfig, "load", classmethod(lambda cls: _config()))
    monkeypatch.setattr(cli, "run_health_checks", lambda _cfg: [CheckResult("x", False, "bad")])
    assert cli.main(["health"]) == 1
    out = capsys.readouterr().out
    assert "0 passed, 1 failed" in out


def test_show_url_requires_explicit_unsafe_flag(monkeypatch, capsys):
    monkeypatch.setattr(cli.AppConfig, "load", classmethod(lambda cls: _config()))
    assert cli.main(["show-url"]) == 2
    assert "--unsafe" in capsys.readouterr().err
