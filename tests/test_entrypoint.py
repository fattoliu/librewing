from pathlib import Path


def test_desktop_entrypoint_uses_launcher():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'librewing = "ssxng.launcher:main"' in pyproject


def test_launcher_uses_status_notifier_tray_and_ng_runtime():
    launcher = Path("ssxng/launcher.py").read_text(encoding="utf-8")
    app = Path("ssxng/app_ng_features.py").read_text(encoding="utf-8")
    assert "from .app_ng_features import main as app_main" in launcher
    assert "class StatusNotifierItem:" in app
    assert "class NgTrayApp:" in app
    assert "Dbusmenu.Server.new" in app
    assert "org.kde.StatusNotifierItem" in app
    assert "NgShadowsocksCore(self.config)" in app
    assert 'gi.require_version("Gtk", "4.0")' in app
    assert 'gi.require_version("Gtk", "3.0")' not in app
    assert "AyatanaAppIndicator" not in app


def test_tray_shutdown_fails_closed_and_stops_services():
    app = Path("ssxng/app_ng_features.py").read_text(encoding="utf-8")
    assert 'self.proxy._gsettings("org.gnome.system.proxy", "mode", "\'none\'")' in app
    assert "for service in (self.http, self.core, self.pac):" in app
    assert "self.indicator.close()" in app
    assert "signal.SIGTERM" in app
    assert "signal.SIGINT" in app
    assert "GLib.unix_signal_add" in app
    assert "app.shutdown_runtime(quit_main=False)" in app


def test_runtime_monitor_fails_closed():
    app = Path("ssxng/app_ng_features.py").read_text(encoding="utf-8")
    assert "def monitor_runtime(self)" in app
    assert "GLib.timeout_add_seconds" in app
    assert "Proxy core stopped unexpectedly" in app


def test_no_legacy_gtk_modules_remain():
    legacy = {
        "app.py",
        "app_beta.py",
        "advanced_settings.py",
        "preferences_ng.py",
        "server_manager.py",
        "share_dialog.py",
        "ui.py",
    }
    assert legacy.isdisjoint({path.name for path in Path("ssxng").glob("*.py")})


def test_librewing_has_its_own_tray_identity():
    app = Path("ssxng/app_ng_features.py").read_text(encoding="utf-8")
    build = Path("scripts/build-deb.sh").read_text(encoding="utf-8")
    icons = {path.name for path in Path("assets/icons").glob("*.svg")}

    assert all(label in app for label in ("Smart Routing", "All Traffic", "Local Proxy Only", "Custom PAC"))
    assert all(label in app for label in ("Import Profiles", "Tools", "Diagnostics", "About LibreWing"))
    assert {
        "librewing.svg",
        "librewing-disabled.svg",
        "librewing-smart.svg",
        "librewing-all.svg",
        "librewing-local.svg",
        "librewing-app.svg",
    } <= icons
    assert not any(Path("assets/upstream").glob("*"))
    assert "assets/upstream" not in build
