from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import webbrowser
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import gi

gi.require_version("Gio", "2.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Dbusmenu", "0.4")
from gi.repository import Dbusmenu, Gdk, GdkPixbuf, Gio, GLib, Gtk  # noqa: E402

from .autostart import is_enabled as autostart_enabled
from .autostart import set_enabled as set_autostart
from .config import AppConfig, LOG_FILE, ServerProfile
from .i18n import tr
from .importer import import_profiles_from_text
from .pac import load_gfwlist_domains
from .plugins import discover_plugins
from .runtime_ng import NgHttpProxyCore, NgPacServer, NgShadowsocksCore, NgSystemProxy
from .screen_qr import ScreenQrError, scan_screen_payloads
from .server_json import example_json, export_servers, load_servers
from .share import build_ss_url, parse_ss_url
from .supervisor import RuntimeEvent, RuntimeSupervisor

APP_ID = "io.github.fattoliu.librewing"
TRAY_ICON_THEME_PATH = "/usr/share/icons/hicolor"
TRAY_ICONS = {
    "off": "librewing-disabled",
    "pac": "librewing-pac",
    "external_pac": "librewing-pac",
    "global": "librewing-global",
    "manual": "librewing-manual",
}

_SNI_XML = """
<node><interface name="org.kde.StatusNotifierItem">
  <method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
  <method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
  <property name="Category" type="s" access="read"/>
  <property name="Id" type="s" access="read"/>
  <property name="Title" type="s" access="read"/>
  <property name="Status" type="s" access="read"/>
  <property name="WindowId" type="i" access="read"/>
  <property name="IconName" type="s" access="read"/>
  <property name="IconPixmap" type="a(iiay)" access="read"/>
  <property name="IconAccessibleDesc" type="s" access="read"/>
  <property name="OverlayIconName" type="s" access="read"/>
  <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
  <property name="AttentionIconName" type="s" access="read"/>
  <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
  <property name="AttentionAccessibleDesc" type="s" access="read"/>
  <property name="AttentionMovieName" type="s" access="read"/>
  <property name="IconThemePath" type="s" access="read"/>
  <property name="Menu" type="o" access="read"/>
  <property name="ItemIsMenu" type="b" access="read"/>
  <signal name="NewIcon"/><signal name="NewStatus"><arg type="s"/></signal><signal name="NewMenu"/>
</interface></node>
"""


def _run_helper(module: str, *args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
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
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _ui4(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return _run_helper("ssxng.modern_ui4", *args, capture=capture)


def _feedback4(*args: str) -> subprocess.CompletedProcess[str]:
    return _run_helper("ssxng.feedback_ui4", *args)


def _spawn_helper(module: str, *args: str) -> None:
    subprocess.Popen(
        [sys.executable, "-m", module, *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )


class StatusNotifierItem:
    """Export a freedesktop tray item without GTK3 or AppIndicator."""

    OBJECT_PATH = "/StatusNotifierItem"
    MENU_PATH = "/MenuBar"

    @staticmethod
    def _icon_pixmap(icon_name: str) -> GLib.Variant:
        path = Path(TRAY_ICON_THEME_PATH) / "36x36/status" / f"{icon_name}.png"
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(path))
        except GLib.Error:
            return GLib.Variant("a(iiay)", [])

        width = pixbuf.get_width()
        height = pixbuf.get_height()
        channels = pixbuf.get_n_channels()
        rowstride = pixbuf.get_rowstride()
        source = pixbuf.get_pixels()
        argb = bytearray()
        for y in range(height):
            row = y * rowstride
            for x in range(width):
                offset = row + x * channels
                red, green, blue = source[offset : offset + 3]
                alpha = source[offset + 3] if channels == 4 else 255
                argb.extend(
                    (
                        alpha,
                        red * alpha // 255,
                        green * alpha // 255,
                        blue * alpha // 255,
                    )
                )
        return GLib.Variant("a(iiay)", [(width, height, bytes(argb))])

    def __init__(self, app: NgTrayApp) -> None:
        self.app = app
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.bus_name = f"{APP_ID}.StatusNotifierItem{os.getpid()}"
        self.icon_name = TRAY_ICONS["off"]
        self._pixmaps: dict[str, GLib.Variant] = {}
        self.menu_server = Dbusmenu.Server.new(self.MENU_PATH)
        node = Gio.DBusNodeInfo.new_for_xml(_SNI_XML)
        interface = node.lookup_interface("org.kde.StatusNotifierItem")
        self.registration_id = self.connection.register_object(
            self.OBJECT_PATH, interface, self._method_call, self._get_property, None
        )
        self.owner_id = Gio.bus_own_name_on_connection(
            self.connection, self.bus_name, Gio.BusNameOwnerFlags.NONE, None, None
        )
        self.watcher_id = Gio.bus_watch_name_on_connection(
            self.connection,
            "org.kde.StatusNotifierWatcher",
            Gio.BusNameWatcherFlags.NONE,
            self._watcher_appeared,
            None,
        )

    def _method_call(
        self, _connection, _sender, _path, _interface, method, _parameters, invocation
    ) -> None:
        if method in ("Activate", "SecondaryActivate"):
            self.app.on_toggle_shadowsocks()
        invocation.return_value(None)

    def _get_property(self, _connection, _sender, _path, _interface, name):
        empty_pixmap = GLib.Variant("a(iiay)", [])
        if self.icon_name not in self._pixmaps:
            self._pixmaps[self.icon_name] = self._icon_pixmap(self.icon_name)
        values = {
            "Category": GLib.Variant("s", "SystemServices"),
            "Id": GLib.Variant("s", "librewing"),
            "Title": GLib.Variant("s", "LibreWing"),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconName": GLib.Variant("s", self.icon_name),
            "IconPixmap": self._pixmaps[self.icon_name],
            "IconAccessibleDesc": GLib.Variant("s", "LibreWing"),
            "OverlayIconName": GLib.Variant("s", ""),
            "OverlayIconPixmap": empty_pixmap,
            "AttentionIconName": GLib.Variant("s", ""),
            "AttentionIconPixmap": empty_pixmap,
            "AttentionAccessibleDesc": GLib.Variant("s", ""),
            "AttentionMovieName": GLib.Variant("s", ""),
            "IconThemePath": GLib.Variant("s", TRAY_ICON_THEME_PATH),
            "Menu": GLib.Variant("o", self.MENU_PATH),
            "ItemIsMenu": GLib.Variant("b", True),
        }
        return values[name]

    def _watcher_appeared(self, _connection, _name, _owner) -> None:
        self.connection.call(
            "org.kde.StatusNotifierWatcher",
            "/StatusNotifierWatcher",
            "org.kde.StatusNotifierWatcher",
            "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (self.bus_name,)),
            None,
            Gio.DBusCallFlags.NONE,
            5000,
            None,
            None,
            None,
        )

    def set_icon(self, icon_name: str) -> None:
        if icon_name != self.icon_name:
            self.icon_name = icon_name
            self.connection.emit_signal(
                None, self.OBJECT_PATH, "org.kde.StatusNotifierItem", "NewIcon", None
            )

    def set_menu(self, root) -> None:
        self.menu_server.set_root(root)
        self.connection.emit_signal(
            None, self.OBJECT_PATH, "org.kde.StatusNotifierItem", "NewMenu", None
        )

    def close(self) -> None:
        Gio.bus_unwatch_name(self.watcher_id)
        Gio.bus_unown_name(self.owner_id)
        self.connection.unregister_object(self.registration_id)


def _menu_item(
    label: str = "",
    callback: Callable[[], None] | None = None,
    *,
    enabled: bool = True,
    toggle: bool = False,
    active: bool = False,
    separator: bool = False,
):
    item = Dbusmenu.Menuitem.new()
    item.property_set_bool(Dbusmenu.MENUITEM_PROP_VISIBLE, True)
    if separator:
        item.property_set(Dbusmenu.MENUITEM_PROP_TYPE, "separator")
        return item
    item.property_set(Dbusmenu.MENUITEM_PROP_LABEL, label)
    item.property_set_bool(Dbusmenu.MENUITEM_PROP_ENABLED, enabled)
    if toggle:
        item.property_set(Dbusmenu.MENUITEM_PROP_TOGGLE_TYPE, Dbusmenu.MENUITEM_TOGGLE_RADIO)
        item.property_set_int(Dbusmenu.MENUITEM_PROP_TOGGLE_STATE, 1 if active else 0)
    if callback is not None:
        item.connect("item-activated", lambda *_args: callback())
    return item


class NgTrayApp:
    """GTK4-era tray controller backed by StatusNotifierItem and DBusMenu."""

    def __init__(self) -> None:
        self.config = AppConfig.load()
        self.core = NgShadowsocksCore(self.config)
        self.http = NgHttpProxyCore(self.config)
        self.proxy = NgSystemProxy(self.config)
        self.pac = NgPacServer(self.config)
        self.loop = GLib.MainLoop()
        self._runtime_shutdown = False
        self._menu_root = None
        self.pac.start()
        self.indicator = StatusNotifierItem(self)
        self.supervisor = RuntimeSupervisor(
            self.config,
            self.core,
            self.http,
            self.pac,
            fail_closed=self._fail_closed,
            emit=self._runtime_event,
        )
        self.rebuild_menu()
        if self.config.profile.server:
            try:
                self.core.start()
                if self.config.http_enabled:
                    self.http.start()
                self.restore_mode()
            except Exception:
                pass

    def alert(self, message: str) -> None:
        _spawn_helper("ssxng.feedback_ui4", "alert", str(message))

    def update_indicator_icon(self) -> None:
        mode = self.config.mode if self.core.running() else "off"
        if mode != "off" and not self.config.show_mode_in_status_bar:
            icon_name = "librewing"
        else:
            icon_name = TRAY_ICONS.get(mode, TRAY_ICONS["off"])
        self.indicator.set_icon(icon_name)

    def ensure_core(self) -> bool:
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

    def restore_mode(self) -> None:
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

    def rebuild_menu(self) -> None:
        running = self.core.running()
        self.update_indicator_icon()
        root = Dbusmenu.Menuitem.new()
        root.property_set_bool(Dbusmenu.MENUITEM_PROP_VISIBLE, True)

        def add(item) -> None:
            root.child_append(item)

        add(_menu_item(f"●  {tr('Shadowsocks: On') if running else tr('Shadowsocks: Off')}", enabled=False))
        add(_menu_item(
            tr("Turn Off Shadowsocks") if running else tr("Turn On Shadowsocks"),
            self.on_toggle_shadowsocks,
        ))
        add(_menu_item(separator=True))
        for label, mode, enabled in (
            ("PAC Auto Mode", "pac", True),
            ("Global Mode", "global", True),
            ("Manual Mode", "manual", True),
            ("External PAC Auto Mode", "external_pac", bool(self.config.external_pac_url.strip())),
        ):
            add(_menu_item(
                tr(label),
                lambda mode=mode: self.on_mode(mode),
                enabled=enabled,
                toggle=True,
                active=self.config.mode == mode,
            ))
        add(_menu_item(separator=True))

        servers = _menu_item(f"{tr('Servers')} - {self.config.profile.name}")
        for index, profile in enumerate(self.config.profiles):
            servers.child_append(_menu_item(
                f"{profile.name} ({profile.server}:{profile.server_port})",
                lambda index=index: self.on_profile(index),
                toggle=True,
                active=index == self.config.active_profile,
            ))
        servers.child_append(_menu_item(separator=True))
        servers.child_append(_menu_item(tr("Server Settings…"), self.on_edit_server))
        add(servers)
        add(_menu_item(tr("Ping Server"), self.on_test_latency))
        add(_menu_item(tr("Scan QR Code on Screen"), self.on_scan_screen_qr))
        add(_menu_item(tr("Import Server URL…"), self.on_import_url))
        add(_menu_item(tr("Import Server URLs From Clipboard"), self.on_import_clipboard))
        add(_menu_item(tr("Import Server Configuration File…"), self.on_import_server_file))
        add(_menu_item(tr("Export All Server Configurations…"), self.on_export_server_file))
        add(_menu_item(tr("Show Example Server Configuration…"), self.on_show_example_server_file))
        add(_menu_item(tr("Share Server Configuration…"), self.on_share_server))
        add(_menu_item(separator=True))
        add(_menu_item(tr("Preferences…"), self.on_preferences))
        add(_menu_item(tr("Copy Terminal Proxy Command"), self.on_copy_terminal_proxy_command))
        add(_menu_item(tr("Update PAC from GFWList"), self.on_update_gfwlist))
        add(_menu_item(tr("Edit PAC User Rules…"), self.on_edit_rules))
        add(_menu_item(separator=True))
        add(_menu_item(tr("View Logs…"), self.on_logs))
        add(_menu_item(tr("Export Diagnostics…"), self.on_export_diagnostics))
        add(_menu_item(tr("Check for Updates…"), self.on_check_updates))
        add(_menu_item(tr("Help"), self.on_help))
        add(_menu_item(tr("About"), self.on_about))
        add(_menu_item(separator=True))
        add(_menu_item(tr("Quit"), self.on_quit))
        self._menu_root = root
        self.indicator.set_menu(root)

    def on_toggle_shadowsocks(self) -> None:
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
            if self.ensure_core():
                try:
                    self.restore_mode()
                except Exception as exc:
                    self.alert(f"Failed to start Shadowsocks:\n{exc}")
        self.rebuild_menu()

    def on_mode(self, mode: str) -> None:
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
            elif self.config.http_enabled:
                self.http.start()
            else:
                self.http.stop()
            if mode != "off":
                self.proxy.apply_exceptions()
        except Exception as exc:
            self.alert(f"Failed to change proxy mode:\n{exc}")
        self.rebuild_menu()

    def on_profile(self, index: int) -> None:
        if index == self.config.active_profile:
            return
        self.config.active_profile = index
        self.config.save()
        try:
            if self.core.running():
                self.core.restart()
            if self.http.running():
                self.http.restart()
            if self.core.running():
                self.restore_mode()
        except Exception as exc:
            self.alert(str(exc))
        self.rebuild_menu()

    def _reload_config(self) -> None:
        fresh = AppConfig.load()
        self.config.__dict__.update(fresh.__dict__)

    def on_edit_server(self) -> None:
        core_running = self.core.running()
        http_running = self.http.running()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "ssxng.server_manager4"],
                check=False,
                start_new_session=True,
            )
            if result.returncode != 0:
                return
            self._reload_config()
            if core_running:
                self.core.restart()
            if http_running:
                self.http.restart() if self.config.http_enabled else self.http.stop()
            if core_running:
                self.restore_mode()
        except Exception as exc:
            self.alert(str(exc))
        finally:
            self.rebuild_menu()

    def on_preferences(self) -> None:
        before = {
            "socks": (
                self.config.socks_listen_address,
                self.config.socks_allow_lan,
                self.config.profile.local_port,
                self.config.socks_timeout,
                self.config.udp_relay,
                self.config.verbose_mode,
            ),
            "pac": (self.config.pac_bind_localhost, self.config.pac_port),
            "http": (
                self.config.http_enabled,
                self.config.http_listen_address,
                self.config.http_allow_lan,
                self.config.http_port,
            ),
        }
        try:
            if _ui4("preferences").returncode != 0:
                return
            self._reload_config()
            set_autostart(self.config.autostart, shutil.which("librewing"))
            after_socks = (
                self.config.socks_listen_address,
                self.config.socks_allow_lan,
                self.config.profile.local_port,
                self.config.socks_timeout,
                self.config.udp_relay,
                self.config.verbose_mode,
            )
            after_pac = (self.config.pac_bind_localhost, self.config.pac_port)
            after_http = (
                self.config.http_enabled,
                self.config.http_listen_address,
                self.config.http_allow_lan,
                self.config.http_port,
            )
            core_running = self.core.running()
            if core_running and before["socks"] != after_socks:
                self.core.restart()
            if before["pac"] != after_pac:
                self.pac.stop()
                self.pac.start()
            if core_running and self.config.http_enabled:
                if before["http"] != after_http or not self.http.running():
                    self.http.restart()
                self.restore_mode()
            elif not self.config.http_enabled or not core_running:
                self.http.stop()
        except Exception as exc:
            self.alert(str(exc))
        finally:
            self.rebuild_menu()

    def _append_imported(self, profiles: list[ServerProfile]) -> int:
        if not profiles:
            return 0
        self.config.profiles.extend(profiles)
        self.config.active_profile = len(self.config.profiles) - len(profiles)
        self.config.save()
        self.rebuild_menu()
        return len(profiles)

    def on_import_url(self) -> None:
        result = _ui4("input", tr("Import Server"), tr("Paste an ss:// URL"), capture=True)
        if result.returncode != 0:
            return
        try:
            count = self._append_imported([parse_ss_url(result.stdout.strip())])
            self.alert(tr("Imported {count} server(s).", count=count))
        except Exception as exc:
            self.alert(f"Import failed:\n{exc}")

    def on_scan_screen_qr(self) -> None:
        try:
            payloads = scan_screen_payloads()
        except ScreenQrError as exc:
            self.alert(f"Screen QR scan failed:\n{exc}")
            return
        count = self._append_imported(
            import_profiles_from_text("\n".join(payloads), self.config.profiles)
        )
        if count:
            self.alert(tr("Imported {count} server(s).", count=count))
        elif payloads:
            self.alert("QR code found, but it did not contain a new valid ss:// server URL.")
        else:
            self.alert(tr("No Shadowsocks QR code was found on the screen."))

    def on_import_clipboard(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            self.alert("No graphical clipboard is available.")
            return

        def finish(clipboard, result, _data) -> None:
            try:
                text = clipboard.read_text_finish(result) or ""
                count = self._append_imported(
                    import_profiles_from_text(text, self.config.profiles)
                )
                if count:
                    self.alert(tr("Imported {count} server(s).", count=count))
                else:
                    self.alert("No new valid ss:// server links found in the clipboard.")
            except Exception as exc:
                self.alert(f"Clipboard import failed:\n{exc}")

        display.get_clipboard().read_text_async(None, finish, None)

    def on_edit_rules(self) -> None:
        try:
            if _ui4("rules").returncode == 0:
                self._reload_config()
                if self.config.mode == "pac":
                    self.proxy.pac_mode()
                self.alert(tr("PAC rules saved. Changes are effective immediately."))
        except Exception as exc:
            self.alert(f"Failed to apply PAC rules:\n{exc}")
        finally:
            self.rebuild_menu()

    def on_update_gfwlist(self) -> None:
        try:
            _feedback4("gfwlist")
            self._reload_config()
        finally:
            self.rebuild_menu()

    def on_test_latency(self) -> None:
        _feedback4("latency")

    def on_logs(self) -> None:
        _spawn_helper("ssxng.modern_ui4", "logs")

    def on_about(self) -> None:
        _spawn_helper("ssxng.feedback_ui4", "about")

    def on_share_server(self) -> None:
        url = build_ss_url(self.config.profile)
        qr_path: Path | None = None
        try:
            args = ["share", self.config.profile.name, url]
            qrencode = shutil.which("qrencode")
            if qrencode:
                tmp = tempfile.NamedTemporaryFile(
                    prefix="ssxng-share-", suffix=".png", delete=False
                )
                qr_path = Path(tmp.name)
                tmp.close()
                subprocess.run(
                    [qrencode, "-o", str(qr_path), "-s", "7", "-m", "2", url],
                    check=True,
                )
                args.extend(["--qr", str(qr_path)])
            _ui4(*args)
        except Exception as exc:
            self.alert(str(exc))
        finally:
            if qr_path is not None:
                qr_path.unlink(missing_ok=True)

    def _choose_file(self, mode: str, title: str, suggested: str = "") -> str | None:
        args = ["file", mode, title]
        if suggested:
            args.extend(["--suggested", suggested])
        result = _ui4(*args, capture=True)
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    def on_import_server_file(self) -> None:
        path = self._choose_file("open", tr("Import Server Configuration File…"))
        if not path:
            return
        try:
            profiles = load_servers(Path(path))
            self._append_imported(profiles)
            self.alert(tr("Imported {count} server(s).", count=len(profiles)))
        except Exception as exc:
            self.alert(str(exc))

    def on_export_server_file(self) -> None:
        path = self._choose_file(
            "save", tr("Export All Server Configurations…"), "shadowsocks-servers.json"
        )
        if not path:
            return
        try:
            export_servers(self.config.profiles, Path(path))
            self.alert(tr("Exported {count} server(s).", count=len(self.config.profiles)))
        except Exception as exc:
            self.alert(str(exc))

    def on_show_example_server_file(self) -> None:
        _spawn_helper(
            "ssxng.modern_ui4",
            "viewer",
            tr("Show Example Server Configuration…"),
            example_json(),
        )

    def on_copy_terminal_proxy_command(self) -> None:
        port = self.config.http_port
        command = (
            f"export http_proxy=http://127.0.0.1:{port}; "
            f"export https_proxy=http://127.0.0.1:{port};"
        )
        display = Gdk.Display.get_default()
        if display is None:
            self.alert("No graphical clipboard is available.")
            return
        display.get_clipboard().set_content(Gdk.ContentProvider.new_for_value(command))
        self.alert(tr("Terminal proxy command copied to clipboard."))

    def diagnostics_text(self) -> str:
        profile = self.config.profile
        plugins = discover_plugins()
        return (
            "LibreWing diagnostics\n"
            f"Generated: {datetime.now().astimezone().isoformat()}\n\n"
            f"Mode: {self.config.mode}\n"
            f"Server: {profile.name} ({profile.server}:{profile.server_port})\n"
            f"ss-local: {'running' if self.core.running() else 'stopped'}\n"
            f"SOCKS5: 127.0.0.1:{profile.local_port}\n"
            f"HTTP bridge: {'running' if self.http.running() else 'stopped'}\n"
            f"HTTP proxy: 127.0.0.1:{self.config.http_port}\n"
            f"PAC: http://127.0.0.1:{self.config.pac_port}/proxy.pac\n"
            f"GFWList domains: {len(load_gfwlist_domains(self.config))}\n"
            f"GFWList updated: {self.config.gfwlist_updated_at or 'never'}\n"
            f"Autostart: {'enabled' if autostart_enabled() else 'disabled'}\n"
            f"Plugins found: {plugins.available_count}\n"
            f"Log: {LOG_FILE}\n"
        )

    def on_export_diagnostics(self) -> None:
        name = f"ShadowsocksX-NG_diagnose_{datetime.now():%Y%m%d_%H%M%S}.txt"
        path = self._choose_file("save", tr("Save Diagnosis to File"), name)
        if not path:
            return
        try:
            Path(path).write_text(self.diagnostics_text(), encoding="utf-8")
            self.alert(tr("Diagnostics exported."))
        except Exception as exc:
            self.alert(str(exc))

    def on_check_updates(self) -> None:
        webbrowser.open("https://github.com/fattoliu/librewing/releases")

    def on_help(self) -> None:
        if not webbrowser.open("https://github.com/fattoliu/librewing"):
            self.alert(tr("Help text"))

    def monitor_runtime(self) -> bool:
        if self._runtime_shutdown:
            return True
        self.supervisor.tick()
        return True

    def _fail_closed(self) -> None:
        try:
            self.proxy._gsettings("org.gnome.system.proxy", "mode", "'none'")
        except Exception:
            pass

    def _runtime_event(self, event: RuntimeEvent) -> None:
        self.rebuild_menu()
        if event.state == "failed" and event.component == "core":
            message = tr(
                "Proxy core stopped unexpectedly. System proxy was disabled to keep networking available."
            )
        elif event.state == "failed":
            message = f"{event.component.upper()} service failed: {event.detail}"
        elif event.state == "restarted":
            message = f"{event.component.upper()} service was restarted automatically."
        else:
            message = f"{event.component.upper()} service recovered."
        self.alert(message)

    def shutdown_runtime(self, *, quit_main: bool = True) -> None:
        if not self._runtime_shutdown:
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
            self.indicator.close()
        if quit_main:
            self.loop.quit()

    def on_quit(self) -> None:
        self.shutdown_runtime()


def _install_signal_handlers(app: NgTrayApp) -> None:
    def shutdown_from_signal() -> bool:
        app.shutdown_runtime()
        return GLib.SOURCE_REMOVE

    for signum in (signal.SIGTERM, signal.SIGINT):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, shutdown_from_signal)


def main() -> int:
    app = None
    try:
        Gtk.init()
        app = NgTrayApp()
        _install_signal_handlers(app)
        GLib.timeout_add_seconds(2, app.monitor_runtime)
        app.loop.run()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"librewing: {exc}", file=sys.stderr)
        return 1
    finally:
        if app is not None:
            app.shutdown_runtime(quit_main=False)


if __name__ == "__main__":
    raise SystemExit(main())
