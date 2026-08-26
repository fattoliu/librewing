from __future__ import annotations

import os

import pytest

from ssxng import plugins


def test_resolve_empty_plugin():
    assert plugins.resolve_plugin("") == ""


def test_resolve_plugin_from_path(tmp_path):
    executable = tmp_path / "obfs-local"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    assert plugins.resolve_plugin(str(executable)) == str(executable)


def test_resolve_plugin_rejects_non_executable(tmp_path):
    plugin = tmp_path / "plugin"
    plugin.write_text("x", encoding="utf-8")
    plugin.chmod(0o644)
    with pytest.raises(ValueError, match="not executable"):
        plugins.resolve_plugin(str(plugin))


def test_discover_plugins(monkeypatch):
    def fake_which(name: str):
        return "/usr/local/bin/obfs-local" if name == "obfs-local" else None

    monkeypatch.setattr(plugins.shutil, "which", fake_which)
    result = plugins.discover_plugins(("obfs-local", "v2ray-plugin"))
    assert result[0].available is True
    assert result[0].path.endswith("obfs-local")
    assert result[1].available is False
