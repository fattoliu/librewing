from __future__ import annotations

from . import app as legacy_app
from . import app_beta
from .advanced_settings import AdvancedPacDialog, AdvancedPreferencesDialog
from .i18n import tr
from .runtime_ng import NgHttpProxyCore, NgPacServer, NgShadowsocksCore, NgSystemProxy


TRAY_ICONS = {
    "off": "shadowsocksx-ng-linux-disabled",
    "pac": "shadowsocksx-ng-linux-pac",
    "external_pac": "shadowsocksx-ng-linux-pac",
    "global": "shadowsocksx-ng-linux-global",
    "manual": "shadowsocksx-ng-linux-manual",
}


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
    del need_http  # Local HTTP is an independent NG preference, not a proxy-mode detail.
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

    actions = {
        "pac": self.proxy.pac_mode,
        "global": self.proxy.global_mode,
        "manual": self.proxy.manual,
        "external_pac": self.proxy.external_pac_mode,
    }
    action = actions.get(self.config.mode)
    if action is not None:
        action()
        self.proxy.apply_exceptions()


def _on_mode(self, item, mode: str) -> None:
    if not item.get_active():
        return
    if mode != "off" and not self.ensure_core():
        return
    try:
        actions = {
            "pac": self.proxy.pac_mode,
            "global": self.proxy.global_mode,
            "manual": self.proxy.manual,
            "external_pac": self.proxy.external_pac_mode,
            "off": self.proxy.off,
        }
        actions[mode]()
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


def _on_advanced_preferences(self, _item) -> None:
    Gtk = legacy_app.Gtk
    dialog = AdvancedPreferencesDialog(self.config)
    try:
        if dialog.run() != Gtk.ResponseType.OK:
            return
        core_running = self.core.running()
        dialog.apply()
        if core_running:
            self.core.restart()
        if self.config.http_enabled and core_running:
            self.http.restart()
        else:
            self.http.stop()
        if core_running:
            self.restore_mode()
        self.alert(tr("Advanced preferences saved."), Gtk.MessageType.INFO)
    except Exception as exc:
        self.alert(str(exc))
    finally:
        dialog.destroy()
        self.rebuild_menu()


def _on_advanced_pac_preferences(self, _item) -> None:
    Gtk = legacy_app.Gtk
    dialog = AdvancedPacDialog(self.config)
    try:
        if dialog.run() != Gtk.ResponseType.OK:
            return
        dialog.apply()
        self.pac.stop()
        self.pac.start()
        if self.core.running():
            self.restore_mode()
        self.alert(tr("Advanced PAC preferences saved."), Gtk.MessageType.INFO)
    except Exception as exc:
        self.alert(str(exc))
    finally:
        dialog.destroy()
        self.rebuild_menu()


def _rebuild_menu(self) -> None:
    Gtk = legacy_app.Gtk
    menu = Gtk.Menu()

    running = self.core.running()
    self.update_indicator_icon()
    status = app_beta._menu_item(
        f"●  {tr('Shadowsocks: On') if running else tr('Shadowsocks: Off')}",
        sensitive=False,
    )
    menu.append(status)
    menu.append(
        app_beta._menu_item(
            tr("Turn Off Shadowsocks") if running else tr("Turn On Shadowsocks"),
            self.on_toggle_shadowsocks,
        )
    )
    menu.append(Gtk.SeparatorMenuItem())

    modes = [
        ("PAC Auto Mode", "pac", True),
        ("Global Mode", "global", True),
        ("Manual Mode", "manual", True),
        ("External PAC Auto Mode", "external_pac", bool(self.config.external_pac_url.strip())),
    ]
    for label, mode, sensitive in modes:
        item = Gtk.CheckMenuItem(label=tr(label))
        item.set_draw_as_radio(True)
        item.set_active(self.config.mode == mode)
        item.set_sensitive(sensitive)
        item.connect("activate", self.on_mode, mode)
        menu.append(item)
    menu.append(Gtk.SeparatorMenuItem())

    servers_item = app_beta._menu_item(f"{tr('Servers')} - {self.config.profile.name}")
    servers = Gtk.Menu()
    servers.append(app_beta._menu_item(tr("Server Settings…"), self.on_edit_server))
    servers.append(Gtk.SeparatorMenuItem())
    for i, profile in enumerate(self.config.profiles):
        item = Gtk.CheckMenuItem(label=f"{profile.name} ({profile.server}:{profile.server_port})")
        item.set_draw_as_radio(True)
        item.set_active(i == self.config.active_profile)
        item.connect("activate", self.on_profile, i)
        servers.append(item)
    servers.show_all()
    servers_item.set_submenu(servers)
    menu.append(servers_item)
    menu.append(app_beta._menu_item(tr("Ping Server"), self.on_test_latency))

    menu.append(app_beta._menu_item(tr("Scan QR Code on Screen"), self.on_scan_screen_qr))
    menu.append(app_beta._menu_item(tr("Import Server URL…"), self.on_import_url))
    menu.append(app_beta._menu_item(tr("Import Server URLs From Clipboard"), self.on_import_clipboard))
    menu.append(app_beta._menu_item(tr("Import Server Configuration File…"), self.on_import_server_file))
    menu.append(app_beta._menu_item(tr("Export All Server Configurations…"), self.on_export_server_file))
    menu.append(app_beta._menu_item(tr("Show Example Server Configuration…"), self.on_show_example_server_file))
    menu.append(app_beta._menu_item(tr("Share Server Configuration…"), self.on_share_server))
    menu.append(app_beta._menu_item(tr("Share All Server URLs…"), self.on_share_all_servers))
    menu.append(Gtk.SeparatorMenuItem())

    autostart_item = Gtk.CheckMenuItem(label=tr("Start At Login"))
    autostart_item.set_active(legacy_app.autostart_enabled())
    autostart_item.connect("activate", self.on_toggle_autostart)
    menu.append(autostart_item)
    menu.append(app_beta._menu_item(tr("Preferences…"), self.on_preferences))
    menu.append(app_beta._menu_item(tr("Advanced Preferences…"), self.on_advanced_preferences))
    menu.append(
        app_beta._menu_item(
            tr("Advanced PAC Proxy Preferences…"), self.on_advanced_pac_preferences
        )
    )
    menu.append(app_beta._menu_item(tr("Copy Terminal Proxy Command"), self.on_copy_terminal_proxy_command))
    menu.append(app_beta._menu_item(tr("Update PAC from GFWList"), self.on_update_gfwlist))
    menu.append(app_beta._menu_item(tr("Edit PAC User Rules…"), self.on_edit_rules))
    menu.append(Gtk.SeparatorMenuItem())

    menu.append(app_beta._menu_item(tr("View Logs…"), self.on_logs))
    menu.append(app_beta._menu_item(tr("Export Diagnostics…"), self.on_export_diagnostics))
    menu.append(app_beta._menu_item(tr("Check for Updates…"), self.on_check_updates))
    menu.append(app_beta._menu_item(tr("Feedback"), self.on_feedback))
    menu.append(app_beta._menu_item(tr("Help"), self.on_help))
    menu.append(app_beta._menu_item(tr("About"), self.on_about))
    menu.append(Gtk.SeparatorMenuItem())
    menu.append(app_beta._menu_item(tr("Quit"), self.on_quit))

    menu.show_all()
    self.indicator.set_menu(menu)


def main() -> int:
    # app_beta is intentionally kept as the stable UI shell. Install the NG
    # runtime implementations before TrayApp is instantiated, then let its
    # existing lifecycle/signal cleanup remain the single owner of shutdown.
    legacy_app.ShadowsocksCore = NgShadowsocksCore
    legacy_app.HttpProxyCore = NgHttpProxyCore
    legacy_app.SystemProxy = NgSystemProxy
    legacy_app.PacServer = NgPacServer

    legacy_app.TrayApp.ensure_core = _ensure_core
    legacy_app.TrayApp.restore_mode = _restore_mode
    legacy_app.TrayApp.on_mode = _on_mode
    legacy_app.TrayApp.on_advanced_preferences = _on_advanced_preferences
    legacy_app.TrayApp.on_advanced_pac_preferences = _on_advanced_pac_preferences

    app_beta._update_indicator_icon = _update_indicator_icon
    app_beta._rebuild_menu = _rebuild_menu
    return app_beta.main()


if __name__ == "__main__":
    raise SystemExit(main())
