from __future__ import annotations

import argparse
import math
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from . import __version__
from .config import AppConfig
from .i18n import system_language, tr
from .pac import update_gfwlist

APP_ID = "io.github.fattoliu.shadowsocksxng.Feedback"
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

        ok = Gtk.Button(label=tr("OK"))
        ok.add_css_class("suggested-action")
        ok.connect("clicked", lambda *_: self.quit())
        _push_actions_to_bottom(body, _bottom_actions(ok))

        win.connect("close-request", self._close)
        win.present()

    def _close(self, *_args) -> bool:
        self.quit()
        return False


class GfwListUpdateApp(Adw.Application):
    """Run one GFWList update in one window and replace progress with result."""

    def __init__(self) -> None:
        super().__init__(application_id=APP_ID + ".GfwList")
        self.config = AppConfig.load()

    def do_activate(self) -> None:
        title = _localize("更新 GFWList", "更新 GFWList", "Update GFWList")
        self.win, body = _base_window(self, title, 470, 180)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.spinner = Gtk.Spinner()
        self.spinner.start()
        row.append(self.spinner)

        self.label = Gtk.Label(
            label=_localize(
                "正在更新 GFWList，请稍候…",
                "正在更新 GFWList，請稍候…",
                "Updating GFWList…",
            ),
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
        try:
            count = update_gfwlist(self.config, timeout=45)
            GLib.idle_add(self._finish, True, str(count))
        except Exception as exc:
            GLib.idle_add(self._finish, False, str(exc))

    def _finish(self, ok: bool, detail: str) -> bool:
        self.spinner.stop()
        self.spinner.set_visible(False)
        if ok:
            self.label.set_text(
                _localize(
                    f"GFWList 更新完成，共载入 {detail} 个域名。",
                    f"GFWList 更新完成，共載入 {detail} 個網域。",
                    f"GFWList updated successfully: {detail} domains.",
                )
            )
        else:
            self.label.set_text(
                _localize(
                    f"GFWList 更新失败：\n{detail}",
                    f"GFWList 更新失敗：\n{detail}",
                    f"GFWList update failed:\n{detail}",
                )
            )

        ok_button = Gtk.Button(label=tr("OK"))
        ok_button.add_css_class("suggested-action")
        ok_button.connect("clicked", lambda *_: self.quit())
        self.actions.append(ok_button)
        return False

    def _close(self, *_args) -> bool:
        self.quit()
        return False


class AboutWindowApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID + ".About")

    def do_activate(self) -> None:
        win = Adw.AboutWindow(
            application=self,
            application_name="ShadowsocksX-NG Linux",
            application_icon="shadowsocksx-ng-linux",
            developer_name="fattoliu",
            version=__version__,
            comments="A practical Shadowsocks desktop client for Linux/Ubuntu",
            website="https://github.com/fattoliu/shadowsocksx-ng-linux",
            issue_url="https://github.com/fattoliu/shadowsocksx-ng-linux/issues",
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
    alert.add_argument("--title", default="ShadowsocksX-NG Linux")
    sub.add_parser("gfwlist")
    sub.add_parser("about")
    args = parser.parse_args()

    if args.cmd == "alert":
        return AlertWindowApp(args.message, args.title).run([sys.argv[0]])
    if args.cmd == "gfwlist":
        return GfwListUpdateApp().run([sys.argv[0]])
    return AboutWindowApp().run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
