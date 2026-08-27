from pathlib import Path


def test_desktop_entrypoint_uses_launcher():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'ssx-ng-linux = "ssxng.launcher:main"' in pyproject


def test_launcher_uses_beta_app_with_server_manager():
    launcher = Path("ssxng/launcher.py").read_text(encoding="utf-8")
    beta = Path("ssxng/app_beta.py").read_text(encoding="utf-8")
    assert "from .app_beta import main as app_main" in launcher
    assert "ServerManagerDialog" in beta
    assert "TrayApp.on_edit_server = _on_edit_server" in beta
    assert "TrayApp.on_add_server = _on_add_server" in beta
    assert "TrayApp.on_delete_server = _on_delete_server" in beta
    assert "legacy_app.HttpProxyCore =" not in beta
    assert "was_http_running = self.http.running()" in beta
    assert "self.http.restart()" in beta


def test_beta_quit_preserves_selected_mode():
    beta = Path("ssxng/app_beta.py").read_text(encoding="utf-8")
    assert "TrayApp.on_quit = _on_quit" in beta
    assert 'self.proxy._gsettings("org.gnome.system.proxy", "mode", "\'none\'")' in beta
    assert "self.proxy.off()" not in beta
    assert "self.http.stop()" in beta
    assert "self.core.stop()" in beta
    assert "self.pac.stop()" in beta
