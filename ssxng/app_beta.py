from __future__ import annotations

import signal
import sys

from . import app as legacy_app
from .server_manager import ServerManagerDialog
from .ui import install_dialog_styles


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


def _on_toggle_shadowsocks(self, _item) -> None:
    if self.core.running():
        try:
            self.proxy.off()
            self.http.stop()
            self.core.stop()
        except Exception as exc:
            self.alert(f"Failed to stop Shadowsocks:\n{exc}")
    else:
        # macOS-style toggle: switching the client back on restores a useful
        # proxy mode instead of leaving the system in Proxy Off.
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
    """Build a macOS ShadowsocksX-NG-style native cascading tray menu."""
    Gtk = legacy_app.Gtk
    menu = Gtk.Menu()

    running = self.core.running()
    status = _menu_item(f"●  Shadowsocks: {'On' if running else 'Off'}", sensitive=False)
    menu.append(status)
    menu.append(_menu_item("Turn Off Shadowsocks" if running else "Turn On Shadowsocks", self.on_toggle_shadowsocks))
    menu.append(Gtk.SeparatorMenuItem())

    # Proxy modes live at the top level, exactly like the macOS client.
    for label, mode in [
        ("PAC Auto Mode", "pac"),
        ("Global Mode", "global"),
        ("Manual Mode", "manual"),
    ]:
        item = Gtk.CheckMenuItem(label=label)
        item.set_draw_as_radio(True)
        item.set_active(self.config.mode == mode)
        item.connect("activate", self.on_mode, mode)
        menu.append(item)

    # Keep the macOS menu position visible even though external PAC mode is not
    # implemented by the Linux client yet.
    menu.append(_menu_item("External PAC Auto Mode", sensitive=False))
    menu.append(Gtk.SeparatorMenuItem())

    # Native Gtk submenu => a separate floating cascade, never an inline
    # accordion/expandable section.
    servers_item = _menu_item(f"Servers - {self.config.profile.name}")
    servers = Gtk.Menu()
    servers.append(_menu_item("Server Settings…", self.on_edit_server))
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

    # macOS places import/share actions directly below the Servers cascade.
    menu.append(_menu_item("Scan QR Code on Screen", sensitive=False))
    menu.append(_menu_item("Import Server URL…", self.on_import_url))
    menu.append(_menu_item("Share Server Configuration…", self.on_copy_url))
    menu.append(Gtk.SeparatorMenuItem())

    menu.append(_menu_item("Preferences…", self.on_preferences))
    menu.append(_menu_item("Copy Terminal Proxy Command", self.on_copy_terminal_proxy_command))
    menu.append(_menu_item("Update PAC from GFWList", self.on_update_gfwlist))
    menu.append(_menu_item("Edit PAC User Rules…", self.on_edit_rules))
    menu.append(Gtk.SeparatorMenuItem())

    menu.append(_menu_item("View Logs…", self.on_logs))
    menu.append(_menu_item("Export Diagnostics…", self.on_diagnostics))
    menu.append(_menu_item("Check for Updates…", self.on_check_updates))
    menu.append(_menu_item("Help", self.on_help))
    menu.append(_menu_item("About", self.on_about))
    menu.append(Gtk.SeparatorMenuItem())
    menu.append(_menu_item("Quit", self.on_quit))

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
    """Stop runtime services without overwriting the selected proxy mode.

    This method is intentionally idempotent because it is used by the tray Quit
    action, Unix signal handlers, and the final cleanup path in ``main``.
    """
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
