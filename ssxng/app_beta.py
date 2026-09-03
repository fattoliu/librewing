from __future__ import annotations

import shutil
import signal
import subprocess
import sys
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path

from . import app as legacy_app
from .i18n import tr
from .screen_qr import ScreenQrError, scan_screen_payloads
from .server_json import example_json, export_servers, load_servers
from .server_manager import ServerManagerDialog
from .ui import create_alert, install_dialog_styles

TRAY_ICON_THEME_PATH = "/usr/share/icons/hicolor/44x44/status"
TRAY_ICONS = {
    "off": "shadowsocksx-ng-linux-disabled",
    "pac": "shadowsocksx-ng-linux-pac",
    "global": "shadowsocksx-ng-linux-global",
    "manual": "shadowsocksx-ng-linux-manual",
}


def _alert(self, message: str, kind=None) -> None:
    Gtk = legacy_app.Gtk
    if kind is None:
        kind = Gtk.MessageType.ERROR
    dialog = create_alert(message, kind)
    dialog.run()
    dialog.destroy()


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
    mode = self.config.mode if self.core.running() else "off"
    icon_name = TRAY_ICONS.get(mode, TRAY_ICONS["off"])
    try:
        self.indicator.set_icon_theme_path(TRAY_ICON_THEME_PATH)
        self.indicator.set_icon_full(icon_name, f"Shadowsocks {mode}")
    except Exception:
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


def _on_toggle_autostart(self, item) -> None:
    enabled = bool(item.get_active())
    try:
        legacy_app.set_autostart(enabled, shutil.which("ssx-ng-linux"))
        self.config.autostart = enabled
        self.config.save()
    except Exception as exc:
        self.alert(str(exc))
    self.rebuild_menu()


def _rebuild_menu(self) -> None:
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
    menu.append(_menu_item(tr("Ping Server"), self.on_test_latency))

    menu.append(_menu_item(tr("Scan QR Code on Screen"), self.on_scan_screen_qr))
    menu.append(_menu_item(tr("Import Server URL…"), self.on_import_url))
    menu.append(_menu_item(tr("Import Server URLs From Clipboard"), self.on_import_clipboard))
    menu.append(_menu_item(tr("Import Server Configuration File…"), self.on_import_server_file))
    menu.append(_menu_item(tr("Export All Server Configurations…"), self.on_export_server_file))
    menu.append(_menu_item(tr("Show Example Server Configuration…"), self.on_show_example_server_file))
    menu.append(_menu_item(tr("Share Server Configuration…"), self.on_share_server))
    menu.append(_menu_item(tr("Share All Server URLs…"), self.on_share_all_servers))
    menu.append(Gtk.SeparatorMenuItem())

    autostart_item = Gtk.CheckMenuItem(label=tr("Start At Login"))
    autostart_item.set_active(legacy_app.autostart_enabled())
    autostart_item.connect("activate", self.on_toggle_autostart)
    menu.append(autostart_item)
    menu.append(_menu_item(tr("Preferences…"), self.on_preferences))
    menu.append(_menu_item(tr("Copy Terminal Proxy Command"), self.on_copy_terminal_proxy_command))
    menu.append(_menu_item(tr("Update PAC from GFWList"), self.on_update_gfwlist))
    menu.append(_menu_item(tr("Edit PAC User Rules…"), self.on_edit_rules))
    menu.append(Gtk.SeparatorMenuItem())

    menu.append(_menu_item(tr("View Logs…"), self.on_logs))
    menu.append(_menu_item(tr("Export Diagnostics…"), self.on_export_diagnostics))
    menu.append(_menu_item(tr("Check for Updates…"), self.on_check_updates))
    menu.append(_menu_item(tr("Feedback"), self.on_feedback))
    menu.append(_menu_item(tr("Help"), self.on_help))
    menu.append(_menu_item(tr("About"), self.on_about))
    menu.append(Gtk.SeparatorMenuItem())
    menu.append(_menu_item(tr("Quit"), self.on_quit))

    menu.show_all()
    self.indicator.set_menu(menu)


def _scan_screen_qr(self, _item) -> None:
    try:
        payloads = scan_screen_payloads()
    except ScreenQrError as exc:
        self.alert(f"Screen QR scan failed:\n{exc}")
        return

    profiles = legacy_app.import_profiles_from_text("\n".join(payloads), self.config.profiles)
    count = self._append_imported(profiles)
    if count:
        self.alert(tr("Imported {count} server(s).", count=count), legacy_app.Gtk.MessageType.INFO)
    elif payloads:
        self.alert("QR code found, but it did not contain a new valid ss:// server URL.", legacy_app.Gtk.MessageType.INFO)
    else:
        self.alert(tr("No Shadowsocks QR code was found on the screen."), legacy_app.Gtk.MessageType.INFO)


def _copy_terminal_proxy_command(self, _item) -> None:
    port = self.config.http_port
    command = (
        f"export http_proxy=http://127.0.0.1:{port}; "
        f"export https_proxy=http://127.0.0.1:{port};"
    )
    clipboard = legacy_app.Gtk.Clipboard.get(legacy_app.Gdk.SELECTION_CLIPBOARD)
    clipboard.set_text(command, -1)
    clipboard.store()
    self.alert(tr("Terminal proxy command copied to clipboard."), legacy_app.Gtk.MessageType.INFO)


def _on_import_server_file(self, _item) -> None:
    Gtk = legacy_app.Gtk
    dialog = Gtk.FileChooserDialog(title=tr("Import Server Configuration File…"), action=Gtk.FileChooserAction.OPEN)
    dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
    try:
        if dialog.run() == Gtk.ResponseType.OK:
            profiles = load_servers(Path(dialog.get_filename()))
            self.config.profiles.extend(profiles)
            self.config.active_profile = len(self.config.profiles) - len(profiles)
            self.config.save()
            self.rebuild_menu()
            self.alert(tr("Imported {count} server(s).", count=len(profiles)), Gtk.MessageType.INFO)
    except Exception as exc:
        self.alert(str(exc))
    finally:
        dialog.destroy()


def _on_export_server_file(self, _item) -> None:
    Gtk = legacy_app.Gtk
    dialog = Gtk.FileChooserDialog(title=tr("Export All Server Configurations…"), action=Gtk.FileChooserAction.SAVE)
    dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
    dialog.set_do_overwrite_confirmation(True)
    dialog.set_current_name("shadowsocks-servers.json")
    try:
        if dialog.run() == Gtk.ResponseType.OK:
            export_servers(self.config.profiles, Path(dialog.get_filename()))
            self.alert(tr("Exported {count} server(s).", count=len(self.config.profiles)), Gtk.MessageType.INFO)
    except Exception as exc:
        self.alert(str(exc))
    finally:
        dialog.destroy()


def _on_show_example_server_file(self, _item) -> None:
    Gtk = legacy_app.Gtk
    dialog = Gtk.Dialog(title=tr("Show Example Server Configuration…"), flags=0)
    dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
    dialog.set_default_size(640, 480)
    scroller = Gtk.ScrolledWindow()
    scroller.set_hexpand(True)
    scroller.set_vexpand(True)
    text = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
    text.get_buffer().set_text(example_json())
    scroller.add(text)
    box = dialog.get_content_area()
    box.set_margin_top(16)
    box.set_margin_bottom(16)
    box.set_margin_start(16)
    box.set_margin_end(16)
    box.add(scroller)
    dialog.show_all()
    dialog.run()
    dialog.destroy()


def _on_share_server(self, _item) -> None:
    Gtk = legacy_app.Gtk
    url = legacy_app.build_ss_url(self.config.profile)
    dialog = Gtk.Dialog(title=tr("Share Server Configuration…"), flags=0)
    dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE, "Copy URL", 1001)
    dialog.set_default_size(460, 500)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin=18)
    dialog.get_content_area().add(box)
    box.pack_start(Gtk.Label(label=self.config.profile.name), False, False, 0)

    qrencode = shutil.which("qrencode")
    qr_path: Path | None = None
    try:
        if qrencode:
            tmp = tempfile.NamedTemporaryFile(prefix="ssxng-share-", suffix=".png", delete=False)
            qr_path = Path(tmp.name)
            tmp.close()
            subprocess.run([qrencode, "-o", str(qr_path), "-s", "7", "-m", "2", url], check=True)
            box.pack_start(Gtk.Image.new_from_file(str(qr_path)), True, True, 0)

        entry = Gtk.Entry(text=url)
        entry.set_editable(False)
        entry.set_hexpand(True)
        box.pack_start(entry, False, False, 0)
        dialog.show_all()
        while True:
            response = dialog.run()
            if response == 1001:
                clipboard = Gtk.Clipboard.get(legacy_app.Gdk.SELECTION_CLIPBOARD)
                clipboard.set_text(url, -1)
                clipboard.store()
                continue
            break
    except Exception as exc:
        self.alert(str(exc))
    finally:
        dialog.destroy()
        if qr_path is not None:
            try:
                qr_path.unlink(missing_ok=True)
            except Exception:
                pass


def _on_share_all_servers(self, _item) -> None:
    Gtk = legacy_app.Gtk
    urls = "\n".join(legacy_app.build_ss_url(profile) for profile in self.config.profiles)
    dialog = Gtk.Dialog(title=tr("Share All Server URLs…"), flags=0)
    dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE, "Copy All", 1001)
    dialog.set_default_size(680, 440)
    scroller = Gtk.ScrolledWindow()
    scroller.set_hexpand(True)
    scroller.set_vexpand(True)
    text = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
    text.get_buffer().set_text(urls)
    scroller.add(text)
    box = dialog.get_content_area()
    box.set_margin_top(16)
    box.set_margin_bottom(16)
    box.set_margin_start(16)
    box.set_margin_end(16)
    box.add(scroller)
    dialog.show_all()
    while True:
        response = dialog.run()
        if response == 1001:
            clipboard = Gtk.Clipboard.get(legacy_app.Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(urls, -1)
            clipboard.store()
            continue
        break
    dialog.destroy()


def _diagnostics_text(self) -> str:
    p = self.config.profile
    plugins = legacy_app.discover_plugins()
    return (
        "ShadowsocksX-NG Linux diagnostics\n"
        f"Generated: {datetime.now().astimezone().isoformat()}\n\n"
        f"Mode: {self.config.mode}\n"
        f"Server: {p.name} ({p.server}:{p.server_port})\n"
        f"ss-local: {'running' if self.core.running() else 'stopped'}\n"
        f"SOCKS5: 127.0.0.1:{p.local_port}\n"
        f"HTTP bridge: {'running' if self.http.running() else 'stopped'}\n"
        f"HTTP proxy: 127.0.0.1:{self.config.http_port}\n"
        f"PAC: http://127.0.0.1:{self.config.pac_port}/proxy.pac\n"
        f"GFWList domains: {len(legacy_app.load_gfwlist_domains(self.config))}\n"
        f"GFWList updated: {self.config.gfwlist_updated_at or 'never'}\n"
        f"Autostart: {'enabled' if legacy_app.autostart_enabled() else 'disabled'}\n"
        f"Plugins found: {plugins.available_count}\n"
        f"Log: {legacy_app.LOG_FILE}\n"
    )


def _on_export_diagnostics(self, _item) -> None:
    Gtk = legacy_app.Gtk
    dialog = Gtk.FileChooserDialog(title=tr("Save Diagnosis to File"), action=Gtk.FileChooserAction.SAVE)
    dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
    dialog.set_do_overwrite_confirmation(True)
    dialog.set_current_name(f"ShadowsocksX-NG_diagnose_{datetime.now():%Y%m%d_%H%M%S}.txt")
    try:
        if dialog.run() == Gtk.ResponseType.OK:
            Path(dialog.get_filename()).write_text(self.diagnostics_text(), encoding="utf-8")
            self.alert(tr("Diagnostics exported."), Gtk.MessageType.INFO)
    except Exception as exc:
        self.alert(str(exc))
    finally:
        dialog.destroy()


def _on_check_updates(self, _item) -> None:
    webbrowser.open("https://github.com/fattoliu/shadowsocksx-ng-linux/releases")


def _on_feedback(self, _item) -> None:
    webbrowser.open("https://github.com/fattoliu/shadowsocksx-ng-linux/issues")


def _on_help(self, _item) -> None:
    if not webbrowser.open("https://github.com/fattoliu/shadowsocksx-ng-linux"):
        self.alert(tr("Help text"), legacy_app.Gtk.MessageType.INFO)


def _shutdown_runtime(self, *, quit_main: bool = True) -> None:
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
    def shutdown_from_signal() -> bool:
        app.shutdown_runtime()
        return False

    for signum in (signal.SIGTERM, signal.SIGINT):
        legacy_app.GLib.unix_signal_add(
            legacy_app.GLib.PRIORITY_DEFAULT,
            signum,
            shutdown_from_signal,
        )


def _monitor_runtime(app) -> bool:
    """Fail closed when ss-local exits while a proxy mode is active."""
    if getattr(app, "_runtime_shutdown", False) or app.config.mode == "off":
        return True
    if app.core.running():
        app._runtime_failure_reported = False
        return True
    if getattr(app, "_runtime_failure_reported", False):
        return True

    app._runtime_failure_reported = True
    try:
        app.proxy._gsettings("org.gnome.system.proxy", "mode", "'none'")
    except Exception:
        pass
    try:
        app.http.stop()
    except Exception:
        pass
    app.update_indicator_icon()
    app.rebuild_menu()
    app.alert(tr("Proxy core stopped unexpectedly. System proxy was disabled to keep networking available."))
    return True


def main() -> int:
    legacy_app.TrayApp.alert = _alert
    legacy_app.TrayApp.on_add_server = _on_add_server
    legacy_app.TrayApp.on_edit_server = _on_edit_server
    legacy_app.TrayApp.on_delete_server = _on_delete_server
    legacy_app.TrayApp.on_toggle_shadowsocks = _on_toggle_shadowsocks
    legacy_app.TrayApp.on_toggle_autostart = _on_toggle_autostart
    legacy_app.TrayApp.update_indicator_icon = _update_indicator_icon
    legacy_app.TrayApp.rebuild_menu = _rebuild_menu
    legacy_app.TrayApp.on_scan_screen_qr = _scan_screen_qr
    legacy_app.TrayApp.on_copy_terminal_proxy_command = _copy_terminal_proxy_command
    legacy_app.TrayApp.on_import_server_file = _on_import_server_file
    legacy_app.TrayApp.on_export_server_file = _on_export_server_file
    legacy_app.TrayApp.on_show_example_server_file = _on_show_example_server_file
    legacy_app.TrayApp.on_share_server = _on_share_server
    legacy_app.TrayApp.on_share_all_servers = _on_share_all_servers
    legacy_app.TrayApp.diagnostics_text = _diagnostics_text
    legacy_app.TrayApp.on_export_diagnostics = _on_export_diagnostics
    legacy_app.TrayApp.on_check_updates = _on_check_updates
    legacy_app.TrayApp.on_feedback = _on_feedback
    legacy_app.TrayApp.on_help = _on_help
    legacy_app.TrayApp.shutdown_runtime = _shutdown_runtime
    legacy_app.TrayApp.on_quit = _on_quit

    app = None
    try:
        install_dialog_styles()
        app = legacy_app.TrayApp()
        app.rebuild_menu()
        _install_signal_handlers(app)
        legacy_app.GLib.timeout_add_seconds(2, _monitor_runtime, app)
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
