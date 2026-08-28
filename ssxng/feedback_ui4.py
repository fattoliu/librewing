from __future__ import annotations

import argparse
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from . import __version__
from .i18n import tr

APP_ID = "io.github.fattoliu.shadowsocksxng.Feedback"


class AlertWindowApp(Adw.Application):
    """A compact standalone libadwaita result window."""

    def __init__(self, message: str, title: str) -> None:
        super().__init__(application_id=APP_ID + ".Alert")
        self.message = message
        self.title = title

    def do_activate(self) -> None:
        win = Adw.ApplicationWindow(application=self)
        win.set_title(self.title)
        # Let GTK calculate the natural height from the message and controls.
        # A fixed 190px height left a conspicuous empty band below short
        # one-line notifications such as "terminal proxy command copied".
        win.set_default_size(420, -1)
        win.set_resizable(False)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label=self.title))
        toolbar.add_top_bar(header)
        try:
            toolbar.set_top_bar_style(Adw.ToolbarStyle.FLAT)
        except Exception:
            pass
        win.set_content(toolbar)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        body.set_margin_top(18)
        body.set_margin_bottom(18)
        body.set_margin_start(20)
        body.set_margin_end(20)
        toolbar.set_content(body)

        label = Gtk.Label(label=self.message, wrap=True, xalign=0)
        label.set_hexpand(True)
        label.set_max_width_chars(52)
        body.append(label)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        actions.set_halign(Gtk.Align.END)
        ok = Gtk.Button(label=tr("OK"))
        ok.add_css_class("suggested-action")
        ok.connect("clicked", lambda *_: self.quit())
        actions.append(ok)
        body.append(actions)

        win.connect("close-request", self._close)
        win.present()

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
    sub.add_parser("about")
    args = parser.parse_args()

    if args.cmd == "alert":
        return AlertWindowApp(args.message, args.title).run([sys.argv[0]])
    return AboutWindowApp().run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
