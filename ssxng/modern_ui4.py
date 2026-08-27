from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from .autostart import is_enabled as autostart_enabled
from .config import AppConfig, LOG_FILE
from .i18n import tr


APP_ID = "io.github.fattoliu.shadowsocksxng.Dialogs"


def _button(label: str, callback, *, suggested: bool = False) -> Gtk.Button:
    button = Gtk.Button(label=label)
    if suggested:
        button.add_css_class("suggested-action")
    button.connect("clicked", callback)
    return button


def _footer(cancel_cb, primary_label: str, primary_cb) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    box.set_halign(Gtk.Align.END)
    box.set_margin_top(12)
    box.set_margin_bottom(16)
    box.set_margin_start(18)
    box.set_margin_end(18)
    box.append(_button(tr("Cancel"), cancel_cb))
    box.append(_button(primary_label, primary_cb, suggested=True))
    return box


def _window(app: Adw.Application, title: str, width: int, height: int) -> tuple[Adw.ApplicationWindow, Adw.ToolbarView, Gtk.Box]:
    win = Adw.ApplicationWindow(application=app)
    win.set_title(title)
    win.set_default_size(width, height)
    toolbar = Adw.ToolbarView()
    header = Adw.HeaderBar()
    header.set_title_widget(Gtk.Label(label=title))
    toolbar.add_top_bar(header)
    win.set_content(toolbar)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    toolbar.set_content(body)
    return win, toolbar, body


class AlertApp(Adw.Application):
    def __init__(self, message: str, title: str = "ShadowsocksX-NG Linux") -> None:
        super().__init__(application_id=APP_ID + ".Alert")
        self.message = message
        self.title = title

    def do_activate(self) -> None:
        parent = Adw.ApplicationWindow(application=self)
        dialog = Adw.AlertDialog.new(self.title, self.message)
        dialog.add_response("ok", tr("OK"))
        dialog.set_default_response("ok")
        dialog.set_close_response("ok")
        dialog.connect("response", lambda *_: self.quit())
        dialog.present(parent)


class TextInputApp(Adw.Application):
    def __init__(self, title: str, placeholder: str) -> None:
        super().__init__(application_id=APP_ID + ".Input")
        self.title = title
        self.placeholder = placeholder
        self.value: str | None = None

    def do_activate(self) -> None:
        self.win, _toolbar, body = _window(self, self.title, 520, 190)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(22)
        content.set_margin_bottom(8)
        content.set_margin_start(22)
        content.set_margin_end(22)
        body.append(content)
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text(self.placeholder)
        self.entry.set_hexpand(True)
        self.entry.connect("activate", self._save)
        content.append(self.entry)
        body.append(_footer(self._cancel, tr("Import"), self._save))
        self.win.connect("close-request", self._close)
        self.win.present()
        self.entry.grab_focus()

    def _save(self, *_args) -> None:
        self.value = self.entry.get_text().strip()
        self.quit()

    def _cancel(self, *_args) -> None:
        self.value = None
        self.quit()

    def _close(self, *_args) -> bool:
        self.value = None
        self.quit()
        return False


class PreferencesApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID + ".Preferences")
        self.config = AppConfig.load()
        self.saved = False

    @staticmethod
    def _entry(text: str = "") -> Gtk.Entry:
        entry = Gtk.Entry(text=text)
        entry.set_hexpand(True)
        return entry

    @staticmethod
    def _spin(value: int, minimum: int = 1, maximum: int = 65535) -> Gtk.SpinButton:
        spin = Gtk.SpinButton.new_with_range(minimum, maximum, 1)
        spin.set_value(value)
        return spin

    @staticmethod
    def _grid() -> Gtk.Grid:
        grid = Gtk.Grid(column_spacing=16, row_spacing=14)
        grid.set_margin_top(22)
        grid.set_margin_bottom(22)
        grid.set_margin_start(26)
        grid.set_margin_end(26)
        grid.set_hexpand(True)
        return grid

    @staticmethod
    def _row(grid: Gtk.Grid, row: int, label: str, widget: Gtk.Widget) -> None:
        grid.attach(Gtk.Label(label=tr(label), halign=Gtk.Align.END, valign=Gtk.Align.CENTER), 0, row, 1, 1)
        widget.set_hexpand(True)
        grid.attach(widget, 1, row, 1, 1)

    def do_activate(self) -> None:
        self.win, toolbar, body = _window(self, tr("Preferences"), 760, 560)
        stack = Adw.ViewStack()
        stack.set_vexpand(True)
        switcher = Adw.ViewSwitcher()
        switcher.set_stack(stack)
        switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        header = toolbar.get_first_child()
        if isinstance(header, Adw.HeaderBar):
            header.set_title_widget(switcher)
        body.append(stack)

        stack.add_titled_with_icon(self._general(), "general", tr("General"), "preferences-system-symbolic")
        stack.add_titled_with_icon(self._advanced(), "advanced", tr("Advanced"), "preferences-other-symbolic")
        stack.add_titled_with_icon(self._http(), "http", "HTTP", "network-server-symbolic")
        stack.add_titled_with_icon(self._network(), "network", tr("Network Interface"), "network-workgroup-symbolic")
        body.append(_footer(self._cancel, tr("Save"), self._save))
        self.win.connect("close-request", self._close)
        self.win.present()

    def _general(self) -> Gtk.Widget:
        grid = self._grid()
        self.autostart = Gtk.CheckButton(label=tr("Start At Login"))
        self.autostart.set_active(autostart_enabled())
        grid.attach(self.autostart, 0, 0, 2, 1)
        self.show_mode = Gtk.CheckButton(label=tr("Show Running Proxy Mode In Status Bar"))
        self.show_mode.set_active(self.config.show_mode_in_status_bar)
        grid.attach(self.show_mode, 0, 1, 2, 1)
        self.gfw_enabled = Gtk.CheckButton(label=tr("Use GFWList"))
        self.gfw_enabled.set_active(self.config.gfwlist_enabled)
        grid.attach(self.gfw_enabled, 0, 2, 2, 1)
        self.gfw_url = self._entry(self.config.gfwlist_url)
        self._row(grid, 3, "GFW List URL:", self.gfw_url)
        return grid

    def _advanced(self) -> Gtk.Widget:
        grid = self._grid()
        self.socks_addr = self._entry(self.config.socks_listen_address)
        self._row(grid, 0, "Local Socks5 Listen Address:", self.socks_addr)
        self.socks_port = self._spin(self.config.profile.local_port, 1024)
        self._row(grid, 1, "Local Socks5 Listen Port:", self.socks_port)
        self.pac_local = Gtk.CheckButton(label=tr("Local PAC Server Bind To Localhost"))
        self.pac_local.set_active(self.config.pac_bind_localhost)
        grid.attach(self.pac_local, 0, 2, 2, 1)
        self.pac_port = self._spin(self.config.pac_port, 1024)
        self._row(grid, 3, "Local PAC Server Listen Port:", self.pac_port)
        self.timeout = self._spin(self.config.socks_timeout, 1, 3600)
        self._row(grid, 4, "Timeout:", self.timeout)
        self.udp = Gtk.CheckButton(label=tr("Enable Udp Replay"))
        self.udp.set_active(self.config.udp_relay)
        grid.attach(self.udp, 0, 5, 2, 1)
        self.verbose = Gtk.CheckButton(label=tr("Enable Verbose Mode"))
        self.verbose.set_active(self.config.verbose_mode)
        grid.attach(self.verbose, 0, 6, 2, 1)
        self.external_url = self._entry(self.config.external_pac_url)
        self.external_url.set_placeholder_text("https://example.com/proxy.pac")
        self._row(grid, 7, "External PAC URL:", self.external_url)
        return grid

    def _http(self) -> Gtk.Widget:
        grid = self._grid()
        self.http_enabled = Gtk.CheckButton(label=tr("HTTP Proxy Enable"))
        self.http_enabled.set_active(self.config.http_enabled)
        grid.attach(self.http_enabled, 0, 0, 2, 1)
        self.http_addr = self._entry(self.config.http_listen_address)
        self._row(grid, 1, "HTTP Proxy Listen Address:", self.http_addr)
        self.http_port = self._spin(self.config.http_port, 1024)
        self._row(grid, 2, "HTTP Proxy Listen Port:", self.http_port)
        self.abp_url = self._entry(self.config.abp_template_url)
        self._row(grid, 3, "ABP PAC engine URL", self.abp_url)
        return grid

    def _network(self) -> Gtk.Widget:
        grid = self._grid()
        self.exceptions = self._entry(self.config.proxy_exceptions)
        self._row(grid, 0, "Bypass proxy settings for these Hosts & Domains:", self.exceptions)
        help_text = Gtk.Label(label=tr("Separate multiple hosts, domains, or networks with commas."), xalign=0, wrap=True)
        help_text.add_css_class("dim-label")
        grid.attach(help_text, 1, 1, 1, 1)
        return grid

    def _save(self, *_args) -> None:
        try:
            external = self.external_url.get_text().strip()
            if external:
                parsed = urlparse(external)
                if parsed.scheme not in ("http", "https") or not parsed.netloc:
                    raise ValueError(tr("External PAC URL must be a valid HTTP or HTTPS URL."))
            socks = self.socks_port.get_value_as_int()
            pac = self.pac_port.get_value_as_int()
            http = self.http_port.get_value_as_int()
            if len({socks, pac, http}) != 3:
                raise ValueError(tr("SOCKS5, PAC and HTTP proxy ports must be different."))
            c = self.config
            c.autostart = self.autostart.get_active()
            c.show_mode_in_status_bar = self.show_mode.get_active()
            c.gfwlist_enabled = self.gfw_enabled.get_active()
            c.gfwlist_url = self.gfw_url.get_text().strip()
            c.socks_listen_address = self.socks_addr.get_text().strip() or "127.0.0.1"
            c.profile.local_port = socks
            c.pac_bind_localhost = self.pac_local.get_active()
            c.pac_port = pac
            c.socks_timeout = self.timeout.get_value_as_int()
            c.udp_relay = self.udp.get_active()
            c.verbose_mode = self.verbose.get_active()
            c.external_pac_url = external
            c.http_enabled = self.http_enabled.get_active()
            c.http_listen_address = self.http_addr.get_text().strip() or "127.0.0.1"
            c.http_port = http
            c.abp_template_url = self.abp_url.get_text().strip()
            c.proxy_exceptions = self.exceptions.get_text().strip()
            c.save()
            self.saved = True
            self.quit()
        except Exception as exc:
            dialog = Adw.AlertDialog.new(tr("Preferences"), str(exc))
            dialog.add_response("ok", tr("OK"))
            dialog.present(self.win)

    def _cancel(self, *_args) -> None:
        self.saved = False
        self.quit()

    def _close(self, *_args) -> bool:
        self.saved = False
        self.quit()
        return False


class RulesApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID + ".Rules")
        self.config = AppConfig.load()
        self.saved = False

    def do_activate(self) -> None:
        self.win, _toolbar, body = _window(self, tr("Edit PAC User Rules…"), 720, 520)
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        wrap.set_margin_top(18)
        wrap.set_margin_start(18)
        wrap.set_margin_end(18)
        wrap.set_vexpand(True)
        body.append(wrap)
        hint = Gtk.Label(label=tr("One rule per line. Adblock/GFWList syntax is supported; @@ rules are DIRECT."), xalign=0, wrap=True)
        hint.add_css_class("dim-label")
        wrap.append(hint)
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        self.text = Gtk.TextView(monospace=True)
        self.text.get_buffer().set_text("\n".join(self.config.custom_rules))
        scroller.set_child(self.text)
        wrap.append(scroller)
        body.append(_footer(self._cancel, tr("Save"), self._save))
        self.win.connect("close-request", self._close)
        self.win.present()

    def _save(self, *_args) -> None:
        buf = self.text.get_buffer()
        raw = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        self.config.custom_rules = [line.strip() for line in raw.splitlines() if line.strip()]
        self.config.save()
        self.saved = True
        self.quit()

    def _cancel(self, *_args) -> None:
        self.quit()

    def _close(self, *_args) -> bool:
        self.quit()
        return False


class LogsApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID + ".Logs")

    def do_activate(self) -> None:
        self.win, _toolbar, body = _window(self, tr("Proxy Logs"), 820, 560)
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_margin_top(12)
        scroller.set_margin_start(16)
        scroller.set_margin_end(16)
        self.text = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
        scroller.set_child(self.text)
        body.append(scroller)
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        footer.set_halign(Gtk.Align.END)
        footer.set_margin_top(12)
        footer.set_margin_bottom(16)
        footer.set_margin_start(16)
        footer.set_margin_end(16)
        footer.append(_button(tr("Clear"), self._clear))
        footer.append(_button(tr("Close"), lambda *_: self.quit(), suggested=True))
        body.append(footer)
        self._refresh()
        self.win.present()

    def _refresh(self) -> None:
        try:
            value = LOG_FILE.read_text(encoding="utf-8", errors="replace") if LOG_FILE.exists() else tr("No proxy log entries yet.")
        except Exception as exc:
            value = str(exc)
        self.text.get_buffer().set_text(value)

    def _clear(self, *_args) -> None:
        try:
            LOG_FILE.write_text("", encoding="utf-8")
        except Exception:
            pass
        self._refresh()


class TextViewerApp(Adw.Application):
    def __init__(self, title: str, text: str) -> None:
        super().__init__(application_id=APP_ID + ".Viewer")
        self.title = title
        self.value = text

    def do_activate(self) -> None:
        win, _toolbar, body = _window(self, self.title, 720, 520)
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_margin_top(16)
        scroller.set_margin_bottom(10)
        scroller.set_margin_start(16)
        scroller.set_margin_end(16)
        text = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
        text.get_buffer().set_text(self.value)
        scroller.set_child(text)
        body.append(scroller)
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        footer.set_halign(Gtk.Align.END)
        footer.set_margin_bottom(16)
        footer.set_margin_end(16)
        footer.append(_button(tr("Close"), lambda *_: self.quit(), suggested=True))
        body.append(footer)
        win.present()


class ShareApp(Adw.Application):
    def __init__(self, name: str, url: str, qr_path: str = "") -> None:
        super().__init__(application_id=APP_ID + ".Share")
        self.name = name
        self.url = url
        self.qr_path = qr_path

    def do_activate(self) -> None:
        win, _toolbar, body = _window(self, tr("Share Server Configuration…"), 500, 560)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content.set_margin_top(18)
        content.set_margin_start(22)
        content.set_margin_end(22)
        content.set_vexpand(True)
        label = Gtk.Label(label=self.name)
        label.add_css_class("title-2")
        content.append(label)
        if self.qr_path and Path(self.qr_path).exists():
            picture = Gtk.Picture.new_for_filename(self.qr_path)
            picture.set_can_shrink(True)
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            picture.set_vexpand(True)
            content.append(picture)
        entry = Gtk.Entry(text=self.url, editable=False)
        content.append(entry)
        body.append(content)
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        footer.set_halign(Gtk.Align.END)
        footer.set_margin_top(10)
        footer.set_margin_bottom(16)
        footer.set_margin_end(18)
        footer.append(_button(tr("Close"), lambda *_: self.quit()))
        footer.append(_button(tr("Copy URL"), self._copy, suggested=True))
        body.append(footer)
        self.win = win
        win.present()

    def _copy(self, *_args) -> None:
        clipboard = self.win.get_clipboard()
        clipboard.set(self.url)


class AboutApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID + ".About")

    def do_activate(self) -> None:
        parent = Adw.ApplicationWindow(application=self)
        dialog = Adw.AboutDialog(
            application_name="ShadowsocksX-NG Linux",
            application_icon="shadowsocksx-ng-linux",
            developer_name="fattoliu",
            version="0.2.0",
            comments="A practical Shadowsocks desktop client for Linux/Ubuntu",
            website="https://github.com/fattoliu/shadowsocksx-ng-linux",
            issue_url="https://github.com/fattoliu/shadowsocksx-ng-linux/issues",
            license_type=Gtk.License.GPL_3_0,
        )
        dialog.connect("closed", lambda *_: self.quit())
        dialog.present(parent)


class FileDialogApp(Adw.Application):
    def __init__(self, mode: str, title: str, suggested: str = "") -> None:
        super().__init__(application_id=APP_ID + ".File")
        self.mode = mode
        self.title = title
        self.suggested = suggested
        self.path: str | None = None

    def do_activate(self) -> None:
        parent = Adw.ApplicationWindow(application=self)
        dialog = Gtk.FileDialog(title=self.title)
        if self.suggested:
            dialog.set_initial_name(self.suggested)
        if self.mode == "open":
            dialog.open(parent, None, self._opened)
        else:
            dialog.save(parent, None, self._saved)

    def _opened(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            file = dialog.open_finish(result)
            self.path = file.get_path()
        except Exception:
            self.path = None
        self.quit()

    def _saved(self, dialog: Gtk.FileDialog, result) -> None:
        try:
            file = dialog.save_finish(result)
            self.path = file.get_path()
        except Exception:
            self.path = None
        self.quit()


def _run(app: Adw.Application) -> int:
    return app.run([sys.argv[0]])


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("alert")
    p.add_argument("message")
    p.add_argument("--title", default="ShadowsocksX-NG Linux")
    p = sub.add_parser("input")
    p.add_argument("title")
    p.add_argument("placeholder")
    sub.add_parser("preferences")
    sub.add_parser("rules")
    sub.add_parser("logs")
    p = sub.add_parser("viewer")
    p.add_argument("title")
    p.add_argument("text")
    p = sub.add_parser("share")
    p.add_argument("name")
    p.add_argument("url")
    p.add_argument("--qr", default="")
    sub.add_parser("about")
    p = sub.add_parser("file")
    p.add_argument("mode", choices=("open", "save"))
    p.add_argument("title")
    p.add_argument("--suggested", default="")
    args = parser.parse_args()

    if args.cmd == "alert":
        _run(AlertApp(args.message, args.title))
        return 0
    if args.cmd == "input":
        app = TextInputApp(args.title, args.placeholder)
        _run(app)
        if app.value is None:
            return 2
        print(app.value)
        return 0
    if args.cmd == "preferences":
        app = PreferencesApp()
        _run(app)
        return 0 if app.saved else 2
    if args.cmd == "rules":
        app = RulesApp()
        _run(app)
        return 0 if app.saved else 2
    if args.cmd == "logs":
        _run(LogsApp())
        return 0
    if args.cmd == "viewer":
        _run(TextViewerApp(args.title, args.text))
        return 0
    if args.cmd == "share":
        _run(ShareApp(args.name, args.url, args.qr))
        return 0
    if args.cmd == "about":
        _run(AboutApp())
        return 0
    if args.cmd == "file":
        app = FileDialogApp(args.mode, args.title, args.suggested)
        _run(app)
        if app.path is None:
            return 2
        print(app.path)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
