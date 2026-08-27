from __future__ import annotations

import signal
import sys

from . import app as legacy_app
from .i18n import tr
from .server_manager import ServerManagerDialog
from .ui import install_dialog_styles

# These names map directly to the original ShadowsocksX-NG @2x menu-bar PNGs
# installed by scripts/build-deb.sh.
TRAY_ICON_THEME_PATH = "/usr/share/icons/hicolor/44x44/status"
TRAY_ICONS = {
    "off": "shadowsocksx-ng-linux-disabled",
    "pac": "shadowsocksx-ng-linux-pac",
    "global": "shadowsocksx-ng-linux-global",
    "manual": "shadowsocksx-ng-linux-manual",
}


def _open_server_manager(self, add_new: bool = False) -> None:
    dialog = ServerManagerDialog(self.config)
    if add_new:
        dialog._on_add(None)
    response = dialog.run()
    if response == legacy_app.Gtk.ResponseType.OK:
        try:
            was_core_running = self.core.running()
            was_http_running = self.http.running()
            dialog.apply()
            if was_core_running:
                self.core.restart()
            if was_http_running:
                self.http.restart()
        except Exception as exc:
            self.alert(f"Failed to save server settings:\n{exc}")
    dialog.destroy()
    self.rebuild_menu()


def _on_add_server(self, _item) -> None:
    _open_server_manager(self, add_new=True)


def _on_edit_server(self, _item) -> None:
    _open_server_manager(self)


def _on_delete_server(self, _item) -> None:
    _open_server_manager(self)


def _menu_item(label, callback=None, *, sensitive=True):
    item = legacy_app.Gtk.MenuItem(label=label)
    item.set_sensitive(sensitive)
    if callback is not None:
        item.connect("activate", callback)
    return item


def _update_indicator_icon(self) -> None:
    """Use the original ShadowsocksX-NG paper-plane status artwork."""
    mode = self.config.mode if self.core.running() else "off"
    icon_name = TRAY_ICONS.get(mode, TRAY_ICONS["off"])
    try:
        self.indicator.set_icon_theme_path(TRAY_ICON_THEME_PATH)
        self.indicator.set_icon_full(icon_name, f"Shadowsocks {mode}")
    except Exception:
        # A visual failure must never affect proxy operation.
        pass


def _on_toggle_shadowsocks(self, _item) -> None:
    if self.core.running():
        try:
            self.proxy.off()
            self.http.stop()
            self.core.stop()
        except Exception as exc:
            self.alert(f"Failed to stop Shadowsocks:\n{exc}")
    else:
        if self.config.mode == "off":
            self.config.mode = "pac"
            self.config.save()
        if self.ensure_core(need_http=self.config.mode in ("pac", "global")):
            try:
                self.restore_mode()
            except Exception as exc:
                self.alert(f"Failed to start Shadowsocks:\n{exc}")
    self.rebuild_menu()


def _rebuild_menu(self) -> None:
    """Build a localized macOS ShadowsocksX-NG-style cascading tray menu."""
    Gtk = legacy_app.Gtk
    menu = Gtk.Menu()

    running = self.core.running()
    self.update_indicator_icon()
    status = _menu_item(
        f"●  {tr('Shadowsocks: On') if running else tr('Shadowsocks: Off')}",
        sensitive=False,
    )
    menu.append(status)
    menu.append(
        _menu_item(
            tr("Turn Off Shadowsocks") if running else tr("Turn On Shadowsocks"),
            self.on_toggle_shadowsocks,
        )
    )
    menu.append(Gtk.SeparatorMenuItem())

    for label, mode in [
        ("PAC Auto Mode", "pac"),
        ("Global Mode", "global"),
        ("Manual Mode", "manual"),
    ]:
        item = Gtk.CheckMenuItem(label=tr(label))
        item.set_draw_as_radio(True)
        item.set_active(self.config.mode == mode)
        item.connect("activate", self.on_mode, mode)
        menu.append(item)

    menu.append(_menu_item(tr("External PAC Auto Mode"), sensitive=False))
    menu.append(Gtk.SeparatorMenuItem())

    # Native Gtk submenu: a separate floating cascade, matching macOS.
    servers_item = _menu_item(f"{tr('Servers')} - {self.config.profile.name}")
    servers = Gtk.Menu()
    servers.append(_menu_item(tr("Server Settings…"), self.on_edit_server))
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

    menu.append(_menu_item(tr("Scan QR Code on Screen"), sensitive=False))
    menu.append(_menu_item(tr("Import Server URL…"), self.on_import_url))
    menu.append(_menu_item(tr("Share Server Configuration…"), self.on_copy_url))
    menu.append(Gtk.SeparatorMenuItem())

    menu.append(_menu_item(tr("Preferences…"), self.on_preferences))
    menu.append(_menu_item(tr("Copy Terminal Proxy Command"), self.on_copy_terminal_proxy_command))
    menu.append(_menu_item(tr("Update PAC from GFWList"), self.on_update_gfwlist))
    menu.append(_menu_item(tr("Edit PAC User Rules…"), self.on_edit_rules))
    menu.append(Gtk.SeparatorMenuItem())

    menu.append(_menu_item(tr("View Logs…"), self.on_logs))
    menu.append(_menu_item(tr("Export Diagnostics…"), self.on_diagnostics))
    menu.append(_menu_item(tr("Check for Updates…"), self.on_check_updates))
    menu.append(_menu_item(tr("Help"), self.on_help))
    menu.append(_menu_item(tr("About"), self.on_about))
    menu.append(Gtk.SeparatorMenuItem())
    menu.append(_menu_item(tr("Quit"), self.on_quit))

    menu.show_all()
    self.indicator.set_menu(menu)


def _copy_terminal_proxy_command(self, _item) -> None:
    port = self.config.http_port
    command = (
        f"export http_proxy=http://127.0.0.1:{port}; "
        f"export https_proxy=http://127.0.0.1:{port}"
    )
    clipboard = legacy_app.Gtk.Clipboard.get(legacy_app.Gdk.SELECTION_CLIPBOARD)
    clipboard.set_text(command, -1)
    clipboard.store()
    self.alert("Terminal proxy command copied to clipboard.", legacy_app.Gtk.MessageType.INFO)


def _on_check_updates(self, _item) -> None:
    self.alert("Update checking is not available yet.", legacy_app.Gtk.MessageType.INFO)


def _on_help(self, _item) -> None:
    self.alert(
        "ShadowsocksX-NG Linux\n\n"
        "Choose a proxy mode, select a server from the Servers submenu, "
        "and use View Logs or Export Diagnostics when troubleshooting.",
        legacy_app.Gtk.MessageType.INFO,
    )


def _shutdown_runtime(self, *, quit_main: bool = True) -> None:
    """Stop runtime services without overwriting the selected proxy mode."""
    if getattr(self, "_runtime_shutdown", False):
        if quit_main:
            legacy_app.Gtk.main_quit()
        return
    self._runtime_shutdown = True

    try:
        self.proxy._gsettings("org.gnome.system.proxy", "mode", "'none'")
    except Exception:
        pass

    for service in (self.http, self.core, self.pac):
        try:
            service.stop()
        except Exception:
            pass

    if quit_main:
        legacy_app.Gtk.main_quit()


def _on_quit(self, _item) -> None:
    self.shutdown_runtime()


def _install_signal_handlers(app) -> None:
    """Route SIGTERM/SIGINT through the same cleanup path as tray Quit."""

    def shutdown_from_signal() -> bool:
        app.shutdown_runtime()
        return False

    for signum in (signal.SIGTERM, signal.SIGINT):
        legacy_app.GLib.unix_signal_add(
            legacy_app.GLib.PRIORITY_DEFAULT,
            signum,
            shutdown_from_signal,
        )


def main() -> int:
    legacy_app.TrayApp.on_add_server = _on_add_server
    legacy_app.TrayApp.on_edit_server = _on_edit_server
    legacy_app.TrayApp.on_delete_server = _on_delete_server
    legacy_app.TrayApp.on_toggle_shadowsocks = _on_toggle_shadowsocks
    legacy_app.TrayApp.update_indicator_icon = _update_indicator_icon
    legacy_app.TrayApp.rebuild_menu = _rebuild_menu
    legacy_app.TrayApp.on_copy_terminal_proxy_command = _copy_terminal_proxy_command
    legacy_app.TrayApp.on_check_updates = _on_check_updates
    legacy_app.TrayApp.on_help = _on_help
    legacy_app.TrayApp.shutdown_runtime = _shutdown_runtime
    legacy_app.TrayApp.on_quit = _on_quit

    app = None
    try:
        install_dialog_styles()
        app = legacy_app.TrayApp()
        # TrayApp builds its first menu before it starts ss-local. Rebuild once
        # after construction so PAC/Global/Manual is reflected immediately on
        # first launch instead of showing the neutral/off icon until a switch.
        app.rebuild_menu()
        _install_signal_handlers(app)
        legacy_app.Gtk.main()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"ssx-ng-linux: {exc}", file=sys.stderr)
        return 1
    finally:
        if app is not None:
            app.shutdown_runtime(quit_main=False)


if __name__ == "__main__":
    raise SystemExit(main())
