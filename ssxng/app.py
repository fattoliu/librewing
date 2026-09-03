from __future__ import annotations

import shutil
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3 as AppIndicator3  # noqa: E402
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from . import __version__
from .autostart import is_enabled as autostart_enabled
from .autostart import set_enabled as set_autostart
from .config import AppConfig, LOG_FILE, ServerProfile
from .core import HttpProxyCore, ShadowsocksCore, SystemProxy
from .diagnostics import tcp_latency, test_http_proxy
from .importer import import_profiles_from_text
from .logs import clear_log, tail_log
from .pac import PacServer, load_gfwlist_domains, update_gfwlist
from .plugins import discover_plugins
from .share import build_ss_url, parse_ss_url

APP_ID = "com.fattoliu.shadowsocksxnglinux"


class ServerDialog(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window | None, profile: ServerProfile):
        super().__init__(title="Server Profile", transient_for=parent, flags=0)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        self.set_default_size(500, 400)
        grid = Gtk.Grid(column_spacing=12, row_spacing=10, margin=16)
        self.get_content_area().add(grid)
        self.entries: dict[str, Gtk.Entry] = {}
        fields = [
            ("name", "Name", profile.name),
            ("server", "Server", profile.server),
            ("server_port", "Server port", str(profile.server_port)),
            ("password", "Password", profile.password),
            ("method", "Cipher", profile.method),
            ("plugin", "Plugin", profile.plugin),
            ("plugin_opts", "Plugin options", profile.plugin_opts),
            ("local_port", "Local SOCKS port", str(profile.local_port)),
        ]
        for row, (key, label, value) in enumerate(fields):
            grid.attach(Gtk.Label(label=label, halign=Gtk.Align.START), 0, row, 1, 1)
            entry = Gtk.Entry(text=value)
            if key == "password":
                entry.set_visibility(False)
            grid.attach(entry, 1, row, 1, 1)
            self.entries[key] = entry
        self.show_all()

    def get_profile(self) -> ServerProfile:
        e = self.entries
        return ServerProfile(
            name=e["name"].get_text().strip() or "Default",
            server=e["server"].get_text().strip(),
            server_port=int(e["server_port"].get_text()),
            password=e["password"].get_text(),
            method=e["method"].get_text().strip(),
            plugin=e["plugin"].get_text().strip(),
            plugin_opts=e["plugin_opts"].get_text().strip(),
            local_port=int(e["local_port"].get_text()),
        )


class RulesDialog(Gtk.Dialog):
    def __init__(self, config: AppConfig):
        super().__init__(title="PAC Rules", flags=0)
        self.config = config
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        self.set_default_size(680, 540)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=16)
        self.get_content_area().add(box)
        self.gfw_enabled = Gtk.CheckButton(label="Use GFWList")
        self.gfw_enabled.set_active(config.gfwlist_enabled)
        box.pack_start(self.gfw_enabled, False, False, 0)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.pack_start(Gtk.Label(label="GFWList URL"), False, False, 0)
        self.gfw_url = Gtk.Entry(text=config.gfwlist_url)
        row.pack_start(self.gfw_url, True, True, 0)
        box.pack_start(row, False, False, 0)
        box.pack_start(
            Gtk.Label(
                label="One rule per line. Adblock/GFWList syntax is supported; @@ rules are DIRECT.",
                halign=Gtk.Align.START,
            ),
            False,
            False,
            0,
        )
        scroller = Gtk.ScrolledWindow()
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        self.text = Gtk.TextView()
        self.text.set_monospace(True)
        self.text.get_buffer().set_text("\n".join(config.custom_rules))
        scroller.add(self.text)
        box.pack_start(scroller, True, True, 0)
        self.show_all()

    def apply(self) -> None:
        buffer = self.text.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        self.config.custom_rules = [line.rstrip() for line in text.splitlines() if line.strip()]
        self.config.gfwlist_enabled = self.gfw_enabled.get_active()
        self.config.gfwlist_url = self.gfw_url.get_text().strip()
        self.config.save()


class PreferencesDialog(Gtk.Dialog):
    def __init__(self, config: AppConfig):
        super().__init__(title="Preferences", flags=0)
        self.config = config
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        self.set_default_size(540, 300)
        grid = Gtk.Grid(column_spacing=12, row_spacing=12, margin=18)
        self.get_content_area().add(grid)

        self.autostart = Gtk.CheckButton(label="Start ShadowsocksX-NG Linux after login")
        self.autostart.set_active(autostart_enabled())
        grid.attach(self.autostart, 0, 0, 2, 1)

        grid.attach(Gtk.Label(label="PAC server port", halign=Gtk.Align.START), 0, 1, 1, 1)
        self.pac_port = Gtk.SpinButton.new_with_range(1024, 65535, 1)
        self.pac_port.set_value(config.pac_port)
        grid.attach(self.pac_port, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label="HTTP proxy port", halign=Gtk.Align.START), 0, 2, 1, 1)
        self.http_port = Gtk.SpinButton.new_with_range(1024, 65535, 1)
        self.http_port.set_value(config.http_port)
        grid.attach(self.http_port, 1, 2, 1, 1)

        grid.attach(Gtk.Label(label="ABP PAC engine URL", halign=Gtk.Align.START), 0, 3, 1, 1)
        self.abp_url = Gtk.Entry(text=config.abp_template_url)
        self.abp_url.set_hexpand(True)
        grid.attach(self.abp_url, 1, 3, 1, 1)
        self.show_all()

    def values(self) -> tuple[int, int, str, bool]:
        return (
            self.pac_port.get_value_as_int(),
            self.http_port.get_value_as_int(),
            self.abp_url.get_text().strip(),
            self.autostart.get_active(),
        )


class TextInputDialog(Gtk.Dialog):
    def __init__(self, title: str, label: str):
        super().__init__(title=title, flags=0)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=16)
        box.pack_start(Gtk.Label(label=label, halign=Gtk.Align.START), False, False, 0)
        self.entry = Gtk.Entry()
        self.entry.set_width_chars(70)
        box.pack_start(self.entry, False, False, 0)
        self.get_content_area().add(box)
        self.show_all()


class LogDialog(Gtk.Dialog):
    def __init__(self):
        super().__init__(title="Proxy Logs", flags=0)
        self.add_buttons("Clear", 1001, Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        self.set_default_size(820, 520)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=12)
        self.get_content_area().add(box)
        label = Gtk.Label(label=str(LOG_FILE), halign=Gtk.Align.START)
        label.set_selectable(True)
        box.pack_start(label, False, False, 0)
        scroller = Gtk.ScrolledWindow()
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        self.text = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
        scroller.add(self.text)
        box.pack_start(scroller, True, True, 0)
        self.refresh()
        self.show_all()

    def refresh(self) -> None:
        value = tail_log(500) or "No proxy log entries yet."
        self.text.get_buffer().set_text(value)


class TrayApp:
    def __init__(self):
        self.config = AppConfig.load()
        self.core = ShadowsocksCore(self.config)
        self.http = HttpProxyCore(self.config)
        self.proxy = SystemProxy(self.config)
        self.pac = PacServer(self.config)
        self.pac.start()
        self.indicator = AppIndicator3.Indicator.new(
            APP_ID, "network-vpn-symbolic", AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("ShadowsocksX-NG Linux")
        self.rebuild_menu()
        if self.config.profile.server:
            try:
                self.core.start()
                if self.config.mode in ("pac", "global"):
                    self.http.start()
                self.restore_mode()
            except Exception:
                pass

    def alert(self, message: str, kind=Gtk.MessageType.ERROR) -> None:
        dialog = Gtk.MessageDialog(message_type=kind, buttons=Gtk.ButtonsType.OK, text=message)
        dialog.run()
        dialog.destroy()

    def restore_mode(self) -> None:
        if self.config.mode == "pac":
            self.proxy.pac_mode()
        elif self.config.mode == "global":
            self.proxy.global_mode()
        elif self.config.mode == "manual":
            self.proxy.manual()

    def rebuild_menu(self) -> None:
        menu = Gtk.Menu()
        status = Gtk.MenuItem(
            label=f"Shadowsocks: {'On' if self.core.running() else 'Off'} · {self.config.profile.name}"
        )
        status.set_sensitive(False)
        menu.append(status)
        menu.append(Gtk.SeparatorMenuItem())

        servers_item = Gtk.MenuItem(label="Servers")
        servers = Gtk.Menu()
        for i, profile in enumerate(self.config.profiles):
            item = Gtk.CheckMenuItem(label=profile.name)
            item.set_draw_as_radio(True)
            item.set_active(i == self.config.active_profile)
            item.connect("activate", self.on_profile, i)
            servers.append(item)
        servers.append(Gtk.SeparatorMenuItem())
        for label, callback in [
            ("Add Server…", self.on_add_server),
            ("Edit Current Server…", self.on_edit_server),
            ("Delete Current Server…", self.on_delete_server),
            ("Import ss:// URL…", self.on_import_url),
            ("Import from Clipboard", self.on_import_clipboard),
            ("Copy Current ss:// URL", self.on_copy_url),
        ]:
            item = Gtk.MenuItem(label=label)
            item.connect("activate", callback)
            servers.append(item)
        servers_item.set_submenu(servers)
        menu.append(servers_item)

        rules_item = Gtk.MenuItem(label="PAC Rules")
        rules = Gtk.Menu()
        for label, callback in [
            ("Edit User Rules…", self.on_edit_rules),
            ("Update GFWList", self.on_update_gfwlist),
        ]:
            item = Gtk.MenuItem(label=label)
            item.connect("activate", callback)
            rules.append(item)
        info = Gtk.MenuItem(label=f"GFWList: {len(load_gfwlist_domains(self.config))} domains")
        info.set_sensitive(False)
        rules.append(info)
        rules_item.set_submenu(rules)
        menu.append(rules_item)
        menu.append(Gtk.SeparatorMenuItem())

        for label, mode in [
            ("PAC Mode", "pac"),
            ("Global Mode", "global"),
            ("Manual Mode", "manual"),
            ("Proxy Off", "off"),
        ]:
            item = Gtk.CheckMenuItem(label=label)
            item.set_draw_as_radio(True)
            item.set_active(self.config.mode == mode)
            item.connect("activate", self.on_mode, mode)
            menu.append(item)

        menu.append(Gtk.SeparatorMenuItem())
        for label, callback in [
            ("Test Server Latency", self.on_test_latency),
            ("Test Proxy Connection", self.on_test_proxy),
            ("Restart Proxy Core", self.on_restart),
            ("Installed Plugins…", self.on_plugins),
            ("View Logs…", self.on_logs),
            ("Diagnostics…", self.on_diagnostics),
            ("Preferences…", self.on_preferences),
            ("About", self.on_about),
            ("Quit", self.on_quit),
        ]:
            item = Gtk.MenuItem(label=label)
            item.connect("activate", callback)
            menu.append(item)
        menu.show_all()
        self.indicator.set_menu(menu)

    def ensure_core(self, need_http: bool = True) -> bool:
        try:
            self.core.start()
            if need_http:
                self.http.start()
            return True
        except Exception as exc:
            self.alert(str(exc))
            return False

    def on_mode(self, item: Gtk.CheckMenuItem, mode: str) -> None:
        if not item.get_active():
            return
        if mode != "off" and not self.ensure_core(need_http=mode in ("pac", "global")):
            return
        try:
            {"pac": self.proxy.pac_mode, "global": self.proxy.global_mode, "manual": self.proxy.manual, "off": self.proxy.off}[mode]()
            if mode not in ("pac", "global"):
                self.http.stop()
            if mode == "off":
                self.core.stop()
        except Exception as exc:
            self.alert(f"Failed to change proxy mode:\n{exc}")
        self.rebuild_menu()

    def on_profile(self, item: Gtk.CheckMenuItem, index: int) -> None:
        if not item.get_active() or index == self.config.active_profile:
            return
        self.config.active_profile = index
        self.config.save()
        try:
            if self.core.running():
                self.core.restart()
            if self.http.running():
                self.http.restart()
        except Exception as exc:
            self.alert(str(exc))
        self.rebuild_menu()

    def edit_profile(self, index: int, is_new: bool = False) -> None:
        profile = ServerProfile(plugin=shutil.which("obfs-local") or "") if is_new else self.config.profiles[index]
        dialog = ServerDialog(None, profile)
        if dialog.run() == Gtk.ResponseType.OK:
            try:
                result = dialog.get_profile()
                if is_new:
                    self.config.profiles.append(result)
                    self.config.active_profile = len(self.config.profiles) - 1
                else:
                    self.config.profiles[index] = result
                self.config.save()
                if self.core.running():
                    self.core.restart()
                if self.http.running():
                    self.http.restart()
            except Exception as exc:
                self.alert(str(exc))
        dialog.destroy()
        self.rebuild_menu()

    def on_add_server(self, _item) -> None:
        self.edit_profile(0, True)

    def on_edit_server(self, _item) -> None:
        self.edit_profile(self.config.active_profile)

    def on_delete_server(self, _item) -> None:
        if len(self.config.profiles) <= 1:
            self.alert("At least one server profile must remain.", Gtk.MessageType.INFO)
            return
        confirm = Gtk.MessageDialog(
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Delete server '{self.config.profile.name}'?",
        )
        response = confirm.run()
        confirm.destroy()
        if response != Gtk.ResponseType.YES:
            return
        del self.config.profiles[self.config.active_profile]
        self.config.active_profile = max(0, min(self.config.active_profile, len(self.config.profiles) - 1))
        self.config.save()
        if self.core.running():
            self.core.restart()
        if self.http.running():
            self.http.restart()
        self.rebuild_menu()

    def _append_imported(self, profiles: list[ServerProfile]) -> int:
        if not profiles:
            return 0
        self.config.profiles.extend(profiles)
        self.config.active_profile = len(self.config.profiles) - len(profiles)
        self.config.save()
        self.rebuild_menu()
        return len(profiles)

    def on_import_url(self, _item) -> None:
        dialog = TextInputDialog("Import Server", "Paste an ss:// URL")
        if dialog.run() == Gtk.ResponseType.OK:
            try:
                profile = parse_ss_url(dialog.entry.get_text())
                count = self._append_imported([profile])
                self.alert(f"Imported {count} server.", Gtk.MessageType.INFO)
            except Exception as exc:
                self.alert(f"Import failed:\n{exc}")
        dialog.destroy()

    def on_import_clipboard(self, _item) -> None:
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = clipboard.wait_for_text() or ""
        profiles = import_profiles_from_text(text, self.config.profiles)
        count = self._append_imported(profiles)
        if count:
            self.alert(f"Imported {count} server{'s' if count != 1 else ''} from clipboard.", Gtk.MessageType.INFO)
        else:
            self.alert("No new valid ss:// server links found in the clipboard.", Gtk.MessageType.INFO)

    def on_copy_url(self, _item) -> None:
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(build_ss_url(self.config.profile), -1)
        clipboard.store()
        self.alert("Current server URL copied to clipboard.", Gtk.MessageType.INFO)

    def on_edit_rules(self, _item) -> None:
        dialog = RulesDialog(self.config)
        if dialog.run() == Gtk.ResponseType.OK:
            dialog.apply()
            self.alert("PAC rules saved. Changes are effective immediately.", Gtk.MessageType.INFO)
        dialog.destroy()
        self.rebuild_menu()

    def on_update_gfwlist(self, _item) -> None:
        def worker() -> None:
            try:
                count = update_gfwlist(self.config)
                GLib.idle_add(self._gfwlist_done, count, None)
            except Exception as exc:
                GLib.idle_add(self._gfwlist_done, 0, str(exc))

        threading.Thread(target=worker, daemon=True).start()
        self.alert("GFWList update started in the background.", Gtk.MessageType.INFO)

    def _gfwlist_done(self, count: int, error: str | None) -> bool:
        if error:
            self.alert(f"GFWList update failed:\n{error}")
        else:
            self.alert(f"GFWList updated: {count} domains.", Gtk.MessageType.INFO)
        self.rebuild_menu()
        return False

    def on_test_latency(self, _item) -> None:
        def worker() -> None:
            try:
                latency = tcp_latency(self.config.profile)
                GLib.idle_add(self.alert, f"Server TCP latency: {latency:.0f} ms", Gtk.MessageType.INFO)
            except Exception as exc:
                GLib.idle_add(self.alert, f"Server latency test failed:\n{exc}")

        threading.Thread(target=worker, daemon=True).start()

    def on_test_proxy(self, _item) -> None:
        if not self.ensure_core(need_http=True):
            return

        def worker() -> None:
            try:
                status, latency = test_http_proxy(self.config)
                GLib.idle_add(
                    self.alert,
                    f"Proxy connection OK (HTTP {status})\nRound trip: {latency:.0f} ms",
                    Gtk.MessageType.INFO,
                )
            except Exception as exc:
                GLib.idle_add(self.alert, f"Proxy connection test failed:\n{exc}")

        threading.Thread(target=worker, daemon=True).start()

    def on_restart(self, _item) -> None:
        try:
            self.core.restart()
            if self.config.mode in ("pac", "global"):
                self.http.restart()
        except Exception as exc:
            self.alert(str(exc))
        self.rebuild_menu()

    def on_plugins(self, _item) -> None:
        plugins = discover_plugins()
        if not plugins:
            message = "No known SIP003 plugins were found in PATH."
        else:
            message = "Installed SIP003 plugins:\n\n" + "\n".join(f"{name}: {path}" for name, path in plugins.items())
        self.alert(message, Gtk.MessageType.INFO)

    def on_logs(self, _item) -> None:
        dialog = LogDialog()
        while True:
            response = dialog.run()
            if response == 1001:
                clear_log()
                dialog.refresh()
                continue
            break
        dialog.destroy()

    def on_preferences(self, _item) -> None:
        dialog = PreferencesDialog(self.config)
        if dialog.run() == Gtk.ResponseType.OK:
            old_pac = self.config.pac_port
            old_http = self.config.http_port
            pac_port, http_port, abp_url, auto = dialog.values()
            if pac_port == http_port:
                self.alert("PAC and HTTP proxy ports must be different.")
            else:
                self.config.pac_port = pac_port
                self.config.http_port = http_port
                self.config.abp_template_url = abp_url
                self.config.autostart = auto
                self.config.save()
                set_autostart(auto, shutil.which("ssx-ng-linux"))
                try:
                    if old_pac != pac_port:
                        self.pac.stop()
                        self.pac.start()
                    if old_http != http_port and self.http.running():
                        self.http.restart()
                    self.restore_mode()
                except Exception as exc:
                    self.alert(f"Preferences saved, but applying them failed:\n{exc}")
        dialog.destroy()
        self.rebuild_menu()

    def on_diagnostics(self, _item) -> None:
        p = self.config.profile
        plugins = discover_plugins()
        self.alert(
            f"Mode: {self.config.mode}\n"
            f"Server: {p.name} ({p.server}:{p.server_port})\n"
            f"ss-local: {'running' if self.core.running() else 'stopped'}\n"
            f"SOCKS5: 127.0.0.1:{p.local_port}\n"
            f"Privoxy: {'running' if self.http.running() else 'stopped'}\n"
            f"HTTP proxy: 127.0.0.1:{self.config.http_port}\n"
            f"PAC: http://127.0.0.1:{self.config.pac_port}/proxy.pac\n"
            f"GFWList domains: {len(load_gfwlist_domains(self.config))}\n"
            f"GFWList updated: {self.config.gfwlist_updated_at or 'never'}\n"
            f"Autostart: {'enabled' if autostart_enabled() else 'disabled'}\n"
            f"Plugins found: {plugins.available_count}\n"
            f"Log: {LOG_FILE}",
            Gtk.MessageType.INFO,
        )

    def on_about(self, _item) -> None:
        dialog = Gtk.AboutDialog(program_name="ShadowsocksX-NG Linux", version=__version__)
        dialog.set_comments("A practical Shadowsocks desktop client for Linux/Ubuntu")
        dialog.set_website("https://github.com/fattoliu/shadowsocksx-ng-linux")
        dialog.set_license_type(Gtk.License.GPL_3_0)
        dialog.run()
        dialog.destroy()

    def on_quit(self, _item) -> None:
        self.proxy.off()
        self.http.stop()
        self.core.stop()
        self.pac.stop()
        Gtk.main_quit()


def main() -> int:
    try:
        TrayApp()
        Gtk.main()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"ssx-ng-linux: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
