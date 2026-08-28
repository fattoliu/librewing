from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from . import app as legacy_app
from . import app_beta
from .config import AppConfig
from .i18n import tr
from .runtime_ng import NgHttpProxyCore, NgPacServer, NgShadowsocksCore, NgSystemProxy
from .server_json import example_json, export_servers, load_servers


TRAY_ICONS = {
    "off": "shadowsocksx-ng-linux-disabled",
    "pac": "shadowsocksx-ng-linux-pac",
    "external_pac": "shadowsocksx-ng-linux-pac",
    "global": "shadowsocksx-ng-linux-global",
    "manual": "shadowsocksx-ng-linux-manual",
}


def _run_helper(module: str, *args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a GTK4 helper modally without sharing the tray's signal group."""
    command = [sys.executable, "-m", module, *args]
    process = subprocess.Popen(
        command,
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate()
    except KeyboardInterrupt:
        process.terminate()
        try:
            process.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        raise
    return subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout if capture else None,
        stderr if capture else None,
    )


def _ui4(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return _run_helper("ssxng.modern_ui4", *args, capture=capture)


def _feedback4(*args: str) -> subprocess.CompletedProcess[str]:
    return _run_helper("ssxng.feedback_ui4", *args)


def _spawn_ui4(*args: str) -> None:
    """Present a non-modal GTK4 window without blocking the GTK3 tray loop."""
    subprocess.Popen(
        [sys.executable, "-m", "ssxng.modern_ui4", *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def _spawn_feedback4(*args: str) -> None:
    """Present standalone feedback that does not require a mapped GTK parent."""
    subprocess.Popen(
        [sys.executable, "-m", "ssxng.feedback_ui4", *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


def _alert4(self, message: str, kind=None) -> None:
    del self, kind
    _spawn_feedback4("alert", str(message))


def _update_indicator_icon(self) -> None:
    mode = self.config.mode if self.core.running() else "off"
    if mode != "off" and not self.config.show_mode_in_status_bar:
        icon_name = "shadowsocksx-ng-linux"
    else:
        icon_name = TRAY_ICONS.get(mode, TRAY_ICONS["off"])
    try:
        self.indicator.set_icon_theme_path(app_beta.TRAY_ICON_THEME_PATH)
        self.indicator.set_icon_full(icon_name, f"Shadowsocks {mode}")
    except Exception:
        pass


def _ensure_core(self, need_http: bool = True) -> bool:
    del need_http
    try:
        self.core.start()
        if self.config.http_enabled:
            self.http.start()
        else:
            self.http.stop()
        return True
    except Exception as exc:
        self.alert(str(exc))
        return False


def _restore_mode(self) -> None:
    if self.core.running() and self.config.http_enabled:
        self.http.start()
    elif not self.config.http_enabled:
        self.http.stop()
    action = {
        "pac": self.proxy.pac_mode,
        "global": self.proxy.global_mode,
        "manual": self.proxy.manual,
        "external_pac": self.proxy.external_pac_mode,
    }.get(self.config.mode)
    if action is not None:
        action()
        self.proxy.apply_exceptions()


def _on_mode(self, item, mode: str) -> None:
    if not item.get_active():
        return
    if mode != "off" and not self.ensure_core():
        return
    try:
        {
            "pac": self.proxy.pac_mode,
            "global": self.proxy.global_mode,
            "manual": self.proxy.manual,
            "external_pac": self.proxy.external_pac_mode,
            "off": self.proxy.off,
        }[mode]()
        if mode == "off":
            self.http.stop()
            self.core.stop()
        else:
            if self.config.http_enabled:
                self.http.start()
            else:
                self.http.stop()
            self.proxy.apply_exceptions()
    except Exception as exc:
        self.alert(f"Failed to change proxy mode:\n{exc}")
    self.rebuild_menu()


def _reload_config(self) -> None:
    fresh = AppConfig.load()
    self.config.__dict__.update(fresh.__dict__)


def _on_edit_server(self, _item) -> None:
    was_core_running = self.core.running()
    was_http_running = self.http.running()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "ssxng.server_manager4"],
            check=False,
            start_new_session=True,
        )
        if result.returncode != 0:
            return
        _reload_config(self)
        if was_core_running:
            self.core.restart()
        if was_http_running:
            if self.config.http_enabled:
                self.http.restart()
            else:
                self.http.stop()
        if was_core_running:
            self.restore_mode()
    except Exception as exc:
        self.alert(str(exc))
    finally:
        self.rebuild_menu()


def _on_preferences(self, _item) -> None:
    before = {
        "socks": (
            self.config.socks_listen_address,
            self.config.profile.local_port,
            self.config.socks_timeout,
            self.config.udp_relay,
            self.config.verbose_mode,
        ),
        "pac": (self.config.pac_bind_localhost, self.config.pac_port),
        "http": (self.config.http_enabled, self.config.http_listen_address, self.config.http_port),
    }
    try:
        result = _ui4("preferences")
        if result.returncode != 0:
            return
        _reload_config(self)
        legacy_app.set_autostart(self.config.autostart, shutil.which("ssx-ng-linux"))

        after_socks = (
            self.config.socks_listen_address,
            self.config.profile.local_port,
            self.config.socks_timeout,
            self.config.udp_relay,
            self.config.verbose_mode,
        )
        after_pac = (self.config.pac_bind_localhost, self.config.pac_port)
        after_http = (self.config.http_enabled, self.config.http_listen_address, self.config.http_port)

        core_running = self.core.running()
        if core_running and before["socks"] != after_socks:
            self.core.restart()
        if before["pac"] != after_pac:
            self.pac.stop()
            self.pac.start()
        if core_running:
            if self.config.http_enabled:
                if before["http"] != after_http or not self.http.running():
                    self.http.restart()
            else:
                self.http.stop()
            self.restore_mode()
        else:
            self.http.stop()
        self.update_indicator_icon()
    except Exception as exc:
        self.alert(str(exc))
    finally:
        self.rebuild_menu()


def _on_import_url4(self, _item) -> None:
    result = _ui4("input", tr("Import Server"), tr("Paste an ss:// URL"), capture=True)
    if result.returncode != 0:
        return
    try:
        value = result.stdout.strip()
        profile = legacy_app.parse_ss_url(value)
        count = self._append_imported([profile])
        self.alert(tr("Imported {count} server(s).", count=count), legacy_app.Gtk.MessageType.INFO)
    except Exception as exc:
        self.alert(f"Import failed:\n{exc}")


def _on_edit_rules4(self, _item) -> None:
    result = _ui4("rules")
    if result.returncode != 0:
        return
    _reload_config(self)
    self.alert(tr("PAC rules saved. Changes are effective immediately."), legacy_app.Gtk.MessageType.INFO)
    self.rebuild_menu()


def _on_update_gfwlist4(self, _item) -> None:
    """One foreground window: progress is replaced by success/error in place."""
    try:
        _feedback4("gfwlist")
        _reload_config(self)
    finally:
        self.rebuild_menu()


def _on_logs4(self, _item) -> None:
    _spawn_ui4("logs")


def _on_about4(self, _item) -> None:
    _spawn_feedback4("about")


def _on_share_server4(self, _item) -> None:
    url = legacy_app.build_ss_url(self.config.profile)
    qr_path: Path | None = None
    try:
        qrencode = shutil.which("qrencode")
        args = ["share", self.config.profile.name, url]
        if qrencode:
            tmp = tempfile.NamedTemporaryFile(prefix="ssxng-share-", suffix=".png", delete=False)
            qr_path = Path(tmp.name)
            tmp.close()
            subprocess.run([qrencode, "-o", str(qr_path), "-s", "7", "-m", "2", url], check=True)
            args.extend(["--qr", str(qr_path)])
        _ui4(*args)
    except Exception as exc:
        self.alert(str(exc))
    finally:
        if qr_path is not None:
            try:
                qr_path.unlink(missing_ok=True)
            except Exception:
                pass


def _on_share_all_servers4(self, _item) -> None:
    urls = "\n".join(legacy_app.build_ss_url(profile) for profile in self.config.profiles)
    _spawn_ui4("viewer", tr("Share All Server URLs…"), urls)


def _choose_file(mode: str, title: str, suggested: str = "") -> str | None:
    args = ["file", mode, title]
    if suggested:
        args.extend(["--suggested", suggested])
    result = _ui4(*args, capture=True)
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _on_import_server_file4(self, _item) -> None:
    path = _choose_file("open", tr("Import Server Configuration File…"))
    if not path:
        return
    try:
        profiles = load_servers(Path(path))
        self.config.profiles.extend(profiles)
        self.config.active_profile = len(self.config.profiles) - len(profiles)
        self.config.save()
        self.rebuild_menu()
        self.alert(tr("Imported {count} server(s).", count=len(profiles)), legacy_app.Gtk.MessageType.INFO)
    except Exception as exc:
        self.alert(str(exc))


def _on_export_server_file4(self, _item) -> None:
    path = _choose_file("save", tr("Export All Server Configurations…"), "shadowsocks-servers.json")
    if not path:
        return
    try:
        export_servers(self.config.profiles, Path(path))
        self.alert(tr("Exported {count} server(s).", count=len(self.config.profiles)), legacy_app.Gtk.MessageType.INFO)
    except Exception as exc:
        self.alert(str(exc))


def _on_show_example_server_file4(self, _item) -> None:
    _spawn_ui4("viewer", tr("Show Example Server Configuration…"), example_json())


def _on_export_diagnostics4(self, _item) -> None:
    name = f"ShadowsocksX-NG_diagnose_{datetime.now():%Y%m%d_%H%M%S}.txt"
    path = _choose_file("save", tr("Save Diagnosis to File"), name)
    if not path:
        return
    try:
        Path(path).write_text(self.diagnostics_text(), encoding="utf-8")
        self.alert(tr("Diagnostics exported."), legacy_app.Gtk.MessageType.INFO)
    except Exception as exc:
        self.alert(str(exc))


def _rebuild_menu(self) -> None:
    """Compact tray hierarchy matching ShadowsocksX-NG."""
    Gtk = legacy_app.Gtk
    menu = Gtk.Menu()

    running = self.core.running()
    self.update_indicator_icon()
    menu.append(app_beta._menu_item(
        f"●  {tr('Shadowsocks: On') if running else tr('Shadowsocks: Off')}", sensitive=False
    ))
    menu.append(app_beta._menu_item(
        tr("Turn Off Shadowsocks") if running else tr("Turn On Shadowsocks"),
        self.on_toggle_shadowsocks,
    ))
    menu.append(Gtk.SeparatorMenuItem())

    for label, mode, sensitive in [
        ("PAC Auto Mode", "pac", True),
        ("Global Mode", "global", True),
        ("Manual Mode", "manual", True),
        ("External PAC Auto Mode", "external_pac", bool(self.config.external_pac_url.strip())),
    ]:
        item = Gtk.CheckMenuItem(label=tr(label))
        item.set_draw_as_radio(True)
        item.set_active(self.config.mode == mode)
        item.set_sensitive(sensitive)
        item.connect("activate", self.on_mode, mode)
        menu.append(item)
    menu.append(Gtk.SeparatorMenuItem())

    servers_item = app_beta._menu_item(f"{tr('Servers')} - {self.config.profile.name}")
    servers = Gtk.Menu()
    for i, profile in enumerate(self.config.profiles):
        item = Gtk.CheckMenuItem(label=f"{profile.name} ({profile.server}:{profile.server_port})")
        item.set_draw_as_radio(True)
        item.set_active(i == self.config.active_profile)
        item.connect("activate", self.on_profile, i)
        servers.append(item)
    servers.append(Gtk.SeparatorMenuItem())
    servers.append(app_beta._menu_item(tr("Server Settings…"), self.on_edit_server))
    servers.show_all()
    servers_item.set_submenu(servers)
    menu.append(servers_item)
    menu.append(app_beta._menu_item(tr("Ping Server"), self.on_test_latency))

    menu.append(app_beta._menu_item(tr("Scan QR Code on Screen"), self.on_scan_screen_qr))
    menu.append(app_beta._menu_item(tr("Import Server URL…"), self.on_import_url))
    menu.append(app_beta._menu_item(tr("Share Server Configuration…"), self.on_share_server))
    menu.append(Gtk.SeparatorMenuItem())

    menu.append(app_beta._menu_item(tr("Preferences…"), self.on_preferences))
    menu.append(app_beta._menu_item(tr("Copy Terminal Proxy Command"), self.on_copy_terminal_proxy_command))
    menu.append(app_beta._menu_item(tr("Update PAC from GFWList"), self.on_update_gfwlist))
    menu.append(app_beta._menu_item(tr("Edit PAC User Rules…"), self.on_edit_rules))
    menu.append(Gtk.SeparatorMenuItem())

    menu.append(app_beta._menu_item(tr("View Logs…"), self.on_logs))
    menu.append(app_beta._menu_item(tr("Export Diagnostics…"), self.on_export_diagnostics))
    menu.append(app_beta._menu_item(tr("Check for Updates…"), self.on_check_updates))
    menu.append(app_beta._menu_item(tr("Help"), self.on_help))
    menu.append(app_beta._menu_item(tr("About"), self.on_about))
    menu.append(Gtk.SeparatorMenuItem())
    menu.append(app_beta._menu_item(tr("Quit"), self.on_quit))

    menu.show_all()
    self.indicator.set_menu(menu)


def main() -> int:
    legacy_app.ShadowsocksCore = NgShadowsocksCore
    legacy_app.HttpProxyCore = NgHttpProxyCore
    legacy_app.SystemProxy = NgSystemProxy
    legacy_app.PacServer = NgPacServer

    legacy_app.TrayApp.ensure_core = _ensure_core
    legacy_app.TrayApp.restore_mode = _restore_mode
    legacy_app.TrayApp.on_mode = _on_mode
    legacy_app.TrayApp.on_preferences = _on_preferences
    legacy_app.TrayApp.on_import_url = _on_import_url4
    legacy_app.TrayApp.on_edit_rules = _on_edit_rules4
    legacy_app.TrayApp.on_update_gfwlist = _on_update_gfwlist4
    legacy_app.TrayApp.on_logs = _on_logs4
    legacy_app.TrayApp.on_about = _on_about4

    # app_beta.main rewires several TrayApp methods from its module-level
    # symbols. Patch those symbols, not only TrayApp, or app_beta.main will
    # silently restore the legacy GTK3 dialogs after this function returns.
    app_beta._alert = _alert4
    app_beta._on_edit_server = _on_edit_server
    app_beta._on_update_gfwlist = _on_update_gfwlist4
    app_beta._on_share_server = _on_share_server4
    app_beta._on_share_all_servers = _on_share_all_servers4
    app_beta._on_import_server_file = _on_import_server_file4
    app_beta._on_export_server_file = _on_export_server_file4
    app_beta._on_show_example_server_file = _on_show_example_server_file4
    app_beta._on_export_diagnostics = _on_export_diagnostics4
    app_beta._update_indicator_icon = _update_indicator_icon
    app_beta._rebuild_menu = _rebuild_menu
    return app_beta.main()


if __name__ == "__main__":
    raise SystemExit(main())
