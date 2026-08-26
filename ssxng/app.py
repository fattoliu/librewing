from __future__ import annotations

import shutil
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3 as AppIndicator3  # noqa: E402
from gi.repository import Gtk  # noqa: E402

from .config import AppConfig, ServerProfile
from .core import ShadowsocksCore, SystemProxy
from .pac import PacServer

APP_ID = "com.fattoliu.shadowsocksxnglinux"


class ServerDialog(Gtk.Dialog):
    def __init__(self, parent: Gtk.Window | None, profile: ServerProfile):
        super().__init__(title="Server Profile", transient_for=parent, flags=0)
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        self.set_default_size(460, 360)
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


class TrayApp:
    def __init__(self):
        self.config = AppConfig.load()
        self.core = ShadowsocksCore(self.config)
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
            except Exception:
                pass

    def alert(self, message: str, kind=Gtk.MessageType.ERROR) -> None:
        d = Gtk.MessageDialog(message_type=kind, buttons=Gtk.ButtonsType.OK, text=message)
        d.run()
        d.destroy()

    def rebuild_menu(self) -> None:
        menu = Gtk.Menu()
        status = Gtk.MenuItem(label=f"Shadowsocks: {'On' if self.core.running() else 'Off'}")
        status.set_sensitive(False)
        menu.append(status)
        menu.append(Gtk.SeparatorMenuItem())

        profiles = Gtk.MenuItem(label="Servers")
        sub = Gtk.Menu()
        for i, profile in enumerate(self.config.profiles):
            item = Gtk.CheckMenuItem(label=profile.name)
            item.set_draw_as_radio(True)
            item.set_active(i == self.config.active_profile)
            item.connect("activate", self.on_profile, i)
            sub.append(item)
        sub.append(Gtk.SeparatorMenuItem())
        add = Gtk.MenuItem(label="Add Server…")
        add.connect("activate", self.on_add_server)
        sub.append(add)
        edit = Gtk.MenuItem(label="Edit Current Server…")
        edit.connect("activate", self.on_edit_server)
        sub.append(edit)
        profiles.set_submenu(sub)
        menu.append(profiles)
        menu.append(Gtk.SeparatorMenuItem())

        for label, mode in [("PAC Mode", "pac"), ("Global Mode", "global"), ("Manual Mode", "manual"), ("Proxy Off", "off")]:
            item = Gtk.CheckMenuItem(label=label)
            item.set_draw_as_radio(True)
            item.set_active(self.config.mode == mode)
            item.connect("activate", self.on_mode, mode)
            menu.append(item)

        menu.append(Gtk.SeparatorMenuItem())
        restart = Gtk.MenuItem(label="Restart ss-local")
        restart.connect("activate", self.on_restart)
        menu.append(restart)
        about = Gtk.MenuItem(label="About")
        about.connect("activate", self.on_about)
        menu.append(about)
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.on_quit)
        menu.append(quit_item)
        menu.show_all()
        self.indicator.set_menu(menu)

    def ensure_core(self) -> bool:
        try:
            self.core.start()
            return True
        except Exception as exc:
            self.alert(str(exc))
            return False

    def on_mode(self, item: Gtk.CheckMenuItem, mode: str) -> None:
        if not item.get_active():
            return
        if mode != "off" and not self.ensure_core():
            return
        try:
            {"pac": self.proxy.pac_mode, "global": self.proxy.global_mode, "manual": self.proxy.manual, "off": self.proxy.off}[mode]()
        except Exception as exc:
            self.alert(f"Failed to change proxy mode:\n{exc}")
        self.rebuild_menu()

    def on_profile(self, item: Gtk.CheckMenuItem, index: int) -> None:
        if not item.get_active() or index == self.config.active_profile:
            return
        self.config.active_profile = index
        self.config.save()
        if self.core.running():
            self.core.restart()
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
            except Exception as exc:
                self.alert(str(exc))
        dialog.destroy()
        self.rebuild_menu()

    def on_add_server(self, _item) -> None:
        self.edit_profile(0, True)

    def on_edit_server(self, _item) -> None:
        self.edit_profile(self.config.active_profile)

    def on_restart(self, _item) -> None:
        try:
            self.core.restart()
        except Exception as exc:
            self.alert(str(exc))
        self.rebuild_menu()

    def on_about(self, _item) -> None:
        dialog = Gtk.AboutDialog(program_name="ShadowsocksX-NG Linux", version="0.1.0")
        dialog.set_comments("Linux/Ubuntu desktop client inspired by ShadowsocksX-NG")
        dialog.set_license_type(Gtk.License.GPL_3_0)
        dialog.run()
        dialog.destroy()

    def on_quit(self, _item) -> None:
        # Match ShadowsocksX-NG behavior: quitting GUI does not disable proxy/core implicitly.
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
