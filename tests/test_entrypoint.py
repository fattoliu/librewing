from pathlib import Path


def test_desktop_entrypoint_uses_launcher():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'ssx-ng-linux = "ssxng.launcher:main"' in pyproject


def test_launcher_uses_ng_feature_app_with_server_manager():
    launcher = Path("ssxng/launcher.py").read_text(encoding="utf-8")
    beta = Path("ssxng/app_beta.py").read_text(encoding="utf-8")
    ng = Path("ssxng/app_ng_features.py").read_text(encoding="utf-8")
    assert "from .app_ng_features import main as app_main" in launcher
    assert "class BetaTrayApp(legacy_app.TrayApp)" in beta
    assert "class NgTrayApp(app_beta.BetaTrayApp)" in ng
    assert "on_edit_server = _on_edit_server" in ng
    assert "on_preferences = _on_preferences" in ng
    assert "shadowsocks_core_class = NgShadowsocksCore" in ng
    assert "http_proxy_core_class = NgHttpProxyCore" in ng
    assert "legacy_app.TrayApp." not in ng


def test_beta_quit_preserves_selected_mode_and_stops_runtime():
    beta = Path("ssxng/app_beta.py").read_text(encoding="utf-8")
    assert "shutdown_runtime = _shutdown_runtime" in beta
    assert "on_quit = _on_quit" in beta
    assert 'self.proxy._gsettings("org.gnome.system.proxy", "mode", "\'none\'")' in beta
    assert "for service in (self.http, self.core, self.pac):" in beta
    assert "service.stop()" in beta
    assert "_runtime_shutdown" in beta


def test_beta_registers_unix_signal_cleanup_and_finally_guard():
    beta = Path("ssxng/app_beta.py").read_text(encoding="utf-8")
    assert "signal.SIGTERM" in beta
    assert "signal.SIGINT" in beta
    assert "GLib.unix_signal_add" in beta
    assert "_install_signal_handlers(app)" in beta
    assert "finally:" in beta
    assert "app.shutdown_runtime(quit_main=False)" in beta


def test_beta_monitors_proxy_core_and_fails_closed():
    beta = Path("ssxng/app_beta.py").read_text(encoding="utf-8")
    assert "def _monitor_runtime(app)" in beta
    assert "GLib.timeout_add_seconds" in beta
    assert 'app.proxy._gsettings("org.gnome.system.proxy", "mode", "\'none\'")' in beta
    assert "Proxy core stopped unexpectedly" in beta
