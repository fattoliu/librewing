from __future__ import annotations

import argparse
import math
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from . import __version__
from .config import AppConfig, GFWLIST_FILE
from .diagnostics import tcp_latency
from .i18n import system_language, tr
from .pac import update_gfwlist

APP_ID = "io.github.fattoliu.librewing.Feedback"
ACTION_BOTTOM = 16


def _localize(zh_cn: str, zh_tw: str, en: str) -> str:
    lang = system_language()
    if lang == "zh_CN":
        return zh_cn
    if lang == "zh_TW":
        return zh_tw
    return en


def _base_window(
    app: Adw.Application,
    title: str,
    width: int,
    height: int,
) -> tuple[Adw.ApplicationWindow, Gtk.Box]:
    win = Adw.ApplicationWindow(application=app)
    win.set_title(title)
    win.set_default_size(width, height)
    win.set_resizable(False)

    toolbar = Adw.ToolbarView()
    header = Adw.HeaderBar()
    header.set_title_widget(Gtk.Label(label=title))
    toolbar.add_top_bar(header)
    try:
        toolbar.set_top_bar_style(Adw.ToolbarStyle.FLAT)
    except Exception:
        pass
    win.set_content(toolbar)

    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    body.set_margin_top(14)
    body.set_margin_bottom(ACTION_BOTTOM)
    body.set_margin_start(18)
    body.set_margin_end(18)
    body.set_vexpand(True)
    toolbar.set_content(body)
    return win, body


def _bottom_actions(*buttons: Gtk.Button) -> Gtk.Box:
    actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    actions.set_halign(Gtk.Align.END)
    for button in buttons:
        actions.append(button)
    return actions


def _push_actions_to_bottom(body: Gtk.Box, actions: Gtk.Box) -> None:
    spacer = Gtk.Box()
    spacer.set_vexpand(True)
    body.append(spacer)
    body.append(actions)


def _ok_button(callback) -> Gtk.Button:
    button = Gtk.Button(label=tr("OK"))
    button.add_css_class("suggested-action")
    button.connect("clicked", callback)
    return button


class AlertWindowApp(Adw.Application):
    """A compact standalone libadwaita result window."""

    def __init__(self, message: str, title: str) -> None:
        super().__init__(application_id=APP_ID + ".Alert")
        self.message = message
        self.title = title

    def _height(self) -> int:
        explicit_lines = max(1, len(self.message.splitlines()))
        wrapped_lines = max(
            1,
            math.ceil(max((len(line) for line in self.message.splitlines()), default=1) / 46),
        )
        lines = max(explicit_lines, wrapped_lines)
        return min(250, 146 + (lines - 1) * 22)

    def do_activate(self) -> None:
        win, body = _base_window(self, self.title, 420, self._height())

        label = Gtk.Label(label=self.message, wrap=True, xalign=0, yalign=0)
        label.set_hexpand(True)
        label.set_max_width_chars(48)
        body.append(label)

        _push_actions_to_bottom(body, _bottom_actions(_ok_button(lambda *_: self.quit())))

        win.connect("close-request", self._close)
        win.present()

    def _close(self, *_args) -> bool:
        self.quit()
        return False


class ProgressResultApp(Adw.Application):
    """Shared one-window progress/result pattern for foreground operations."""

    def __init__(self, application_id: str, title: str, progress_text: str, width: int = 470) -> None:
        super().__init__(application_id=application_id)
        self.title = title
        self.progress_text = progress_text
        self.width = width

    def do_activate(self) -> None:
        self.win, body = _base_window(self, self.title, self.width, 180)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.spinner = Gtk.Spinner()
        self.spinner.start()
        row.append(self.spinner)

        self.label = Gtk.Label(
            label=self.progress_text,
            wrap=True,
            xalign=0,
            yalign=0,
        )
        self.label.set_hexpand(True)
        self.label.set_max_width_chars(56)
        row.append(self.label)
        body.append(row)

        self.actions = _bottom_actions()
        _push_actions_to_bottom(body, self.actions)

        self.win.connect("close-request", self._close)
        self.win.present()
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        raise NotImplementedError

    def _show_result(self, text: str) -> bool:
        self.spinner.stop()
        self.spinner.set_visible(False)
        self.label.set_text(text)
        self.actions.append(_ok_button(lambda *_: self.quit()))
        return False

    def _close(self, *_args) -> bool:
        self.quit()
        return False


class GfwListUpdateApp(ProgressResultApp):
    """Run one GFWList update in one window and replace progress with result."""

    def __init__(self) -> None:
        super().__init__(
            APP_ID + ".GfwList",
            _localize("更新 GFWList", "更新 GFWList", "Update GFWList"),
            _localize(
                "正在更新 GFWList，请稍候…",
                "正在更新 GFWList，請稍候…",
                "Updating GFWList…",
            ),
        )
        self.config = AppConfig.load()

    def _refresh_active_pac(self) -> None:
        if self.config.mode != "pac" or not GFWLIST_FILE.exists():
            return
        revision = int(GFWLIST_FILE.stat().st_mtime_ns)
        url = f"http://127.0.0.1:{self.config.pac_port}/proxy.pac?v={revision}"
        subprocess.run(
            ["gsettings", "set", "org.gnome.system.proxy", "autoconfig-url", repr(url)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["gsettings", "set", "org.gnome.system.proxy", "mode", "'auto'"],
            check=True,
            capture_output=True,
            text=True,
        )

    def _worker(self) -> None:
        try:
            count = update_gfwlist(self.config, timeout=45)
            self._refresh_active_pac()
            text = _localize(
                f"GFWList 更新完成，共载入 {count} 个域名。",
                f"GFWList 更新完成，共載入 {count} 個網域。",
                f"GFWList updated successfully: {count} domains.",
            )
        except Exception as exc:
            text = _localize(
                f"GFWList 更新失败：\n{exc}",
                f"GFWList 更新失敗：\n{exc}",
                f"GFWList update failed:\n{exc}",
            )
        GLib.idle_add(self._show_result, text)


class LatencyTestApp(ProgressResultApp):
    """Show progress immediately, then replace it with the TCP latency result."""

    def __init__(self) -> None:
        self.config = AppConfig.load()
        profile = self.config.profile
        super().__init__(
            APP_ID + ".Latency",
            _localize("服务器测速", "伺服器測速", "Server Latency Test"),
            _localize(
                f"正在测试 {profile.name}（{profile.server}:{profile.server_port}），请稍候…",
                f"正在測試 {profile.name}（{profile.server}:{profile.server_port}），請稍候…",
                f"Testing {profile.name} ({profile.server}:{profile.server_port})…",
            ),
        )

    def _worker(self) -> None:
        profile = self.config.profile
        try:
            latency = tcp_latency(profile)
            text = _localize(
                f"服务器 TCP 延迟：{latency:.0f} ms",
                f"伺服器 TCP 延遲：{latency:.0f} ms",
                f"Server TCP latency: {latency:.0f} ms",
            )
        except Exception as exc:
            text = _localize(
                f"服务器测速失败：\n{exc}",
                f"伺服器測速失敗：\n{exc}",
                f"Server latency test failed:\n{exc}",
            )
        GLib.idle_add(self._show_result, text)


class AboutWindowApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID + ".About")

    def do_activate(self) -> None:
        win = Adw.AboutWindow(
            application=self,
            application_name="LibreWing",
            application_icon="librewing",
            developer_name="fattoliu",
            version=__version__,
            comments=tr("A practical Shadowsocks desktop client for Linux/Ubuntu"),
            website="https://github.com/fattoliu/librewing",
            issue_url="https://github.com/fattoliu/librewing/issues",
            license_type=Gtk.License.GPL_3_0,
        )
        win.connect("close-request", self._close)
        win.present()

    def _close(self, *_args) -> bool:
        self.quit()
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    alert = sub.add_parser("alert")
    alert.add_argument("message")
    alert.add_argument("--title", default="LibreWing")
    sub.add_parser("gfwlist")
    sub.add_parser("latency")
    sub.add_parser("about")
    args = parser.parse_args()

    if args.cmd == "alert":
        return AlertWindowApp(args.message, args.title).run([sys.argv[0]])
    if args.cmd == "gfwlist":
        return GfwListUpdateApp().run([sys.argv[0]])
    if args.cmd == "latency":
        return LatencyTestApp().run([sys.argv[0]])
    return AboutWindowApp().run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
