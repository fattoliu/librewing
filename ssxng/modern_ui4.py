from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from .autostart import is_enabled as autostart_enabled
from .config import AppConfig, LOG_FILE
from .i18n import system_language, tr

APP_ID = "io.github.fattoliu.shadowsocksxng.Dialogs"
PAGE_PAD = 24
ACTION_BOTTOM = 16
GROUP_GAP = 20
CONTROL_GAP = 12

_EXTRA_I18N = {
    "zh_CN": {
        "General": "常规",
        "Advanced": "高级",
        "Network Interface": "网络接口",
        "Import": "导入",
        "Copy URL": "复制 URL",
        "Proxy behavior": "代理行为",
        "PAC service": "PAC 服务",
        "HTTP service": "HTTP 服务",
        "Network exceptions": "网络例外",
        "Separate multiple hosts, domains, or networks with commas.": "多个主机、域名或网段请使用逗号分隔。",
        "SOCKS5, PAC and HTTP proxy ports must be different.": "SOCKS5、PAC 和 HTTP 代理端口不能相同。",
    },
    "zh_TW": {
        "General": "一般",
        "Advanced": "進階",
        "Network Interface": "網路介面",
        "Import": "匯入",
        "Copy URL": "複製 URL",
        "Proxy behavior": "代理行為",
        "PAC service": "PAC 服務",
        "HTTP service": "HTTP 服務",
        "Network exceptions": "網路例外",
        "Separate multiple hosts, domains, or networks with commas.": "多個主機、網域或網段請使用逗號分隔。",
        "SOCKS5, PAC and HTTP proxy ports must be different.": "SOCKS5、PAC 與 HTTP 代理連接埠不能相同。",
    },
}


def _t(text: str) -> str:
    return _EXTRA_I18N.get(system_language(), {}).get(text, tr(text))


def _button(label: str, callback, *, suggested: bool = False) -> Gtk.Button:
    button = Gtk.Button(label=label)
    if suggested:
        button.add_css_class("suggested-action")
    button.connect("clicked", callback)
    return button


def _footer(cancel_cb, primary_label: str, primary_cb) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    box.set_halign(Gtk.Align.END)
    box.set_margin_top(18)
    box.set_margin_bottom(ACTION_BOTTOM)
    box.set_margin_start(PAGE_PAD)
    box.set_margin_end(PAGE_PAD)
    box.append(_button(tr("Cancel"), cancel_cb))
    box.append(_button(primary_label, primary_cb, suggested=True))
    return box


def _single_footer(label: str, callback, *, suggested: bool = True) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    box.set_halign(Gtk.Align.END)
    box.set_margin_top(18)
    box.set_margin_bottom(ACTION_BOTTOM)
    box.set_margin_start(PAGE_PAD)
    box.set_margin_end(PAGE_PAD)
    box.append(_button(label, callback, suggested=suggested))
    return box


def _window(
    app: Adw.Application,
    title: str,
    width: int,
    height: int,
) -> tuple[Adw.ApplicationWindow, Adw.ToolbarView, Gtk.Box]:
    win = Adw.ApplicationWindow(application=app)
    win.set_title(title)
    win.set_default_size(width, height)
    toolbar = Adw.ToolbarView()
    header = Adw.HeaderBar()
    header.set_title_widget(Gtk.Label(label=title))
    toolbar.add_top_bar(header)
    try:
        toolbar.set_top_bar_style(Adw.ToolbarStyle.FLAT)
    except Exception:
        pass
    win.set_content(toolbar)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    toolbar.set_content(body)
    return win, toolbar, body


def _page_wrap(child: Gtk.Widget, *, top: int = PAGE_PAD, bottom: int = 8) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.set_margin_top(top)
    box.set_margin_bottom(bottom)
    box.set_margin_start(PAGE_PAD)
    box.set_margin_end(PAGE_PAD)
    box.set_vexpand(True)
    box.append(child)
    return box


def _compact_tab(label: str, icon_name: str, stack: Adw.ViewStack, page_name: str) -> Gtk.ToggleButton:
    content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
    icon = Gtk.Image.new_from_icon_name(icon_name)
    icon.set_pixel_size(16)
    text = Gtk.Label(label=label)
    content.append(icon)
    content.append(text)
    button = Gtk.ToggleButton()
    button.set_child(content)
    button.add_css_class("flat")
    button.connect(
        "toggled",
        lambda btn: stack.set_visible_child_name(page_name) if btn.get_active() else None,
    )
    return button


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
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=CONTROL_GAP)
        content.set_margin_top(PAGE_PAD)
        content.set_margin_start(PAGE_PAD)
        content.set_margin_end(PAGE_PAD)
        content.set_vexpand(True)
        body.append(content)
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text(self.placeholder)
        self.entry.set_hexpand(True)
        self.entry.connect("activate", self._save)
        content.append(self.entry)
        body.append(_footer(self._cancel, _t("Import"), self._save))
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
    def _entry_row(title: str, text: str = "") -> Adw.EntryRow:
        row = Adw.EntryRow(title=title)
        row.set_text(text)
        return row

    @staticmethod
    def _switch_row(title: str, active: bool) -> Adw.SwitchRow:
        row = Adw.SwitchRow(title=title)
        row.set_active(active)
        return row

    @staticmethod
    def _spin_row(title: str, value: int, minimum: int = 1, maximum: int = 65535) -> Adw.SpinRow:
        adjustment = Gtk.Adjustment(value=value, lower=minimum, upper=maximum, step_increment=1, page_increment=10)
        return Adw.SpinRow(title=title, adjustment=adjustment)

    @staticmethod
    def _group(title: str = "") -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup()
        if title:
            group.set_title(title)
        return group

    @staticmethod
    def _page(*groups: Adw.PreferencesGroup) -> Gtk.ScrolledWindow:
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=GROUP_GAP)
        content.set_margin_top(PAGE_PAD)
        content.set_margin_bottom(PAGE_PAD)
        content.set_margin_start(PAGE_PAD)
        content.set_margin_end(PAGE_PAD)
        for group in groups:
            content.append(group)
        clamp = Adw.Clamp(maximum_size=720, tightening_threshold=620)
        clamp.set_child(content)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(clamp)
        return scroller

    def do_activate(self) -> None:
        self.win, _toolbar, body = _window(self, tr("Preferences"), 780, 600)
        stack = Adw.ViewStack()
        stack.set_vexpand(True)
        stack.add_named(self._general(), "general")
        stack.add_named(self._advanced(), "advanced")
        stack.add_named(self._http(), "http")
        stack.add_named(self._network(), "network")

        tabs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tabs.set_halign(Gtk.Align.CENTER)
        tabs.set_margin_top(14)
        tabs.set_margin_bottom(4)
        tab_specs = [
            (_t("General"), "preferences-system-symbolic", "general"),
            (_t("Advanced"), "preferences-other-symbolic", "advanced"),
            ("HTTP", "network-server-symbolic", "http"),
            (_t("Network Interface"), "network-workgroup-symbolic", "network"),
        ]
        first = None
        previous = None
        for label, icon_name, page_name in tab_specs:
            button = _compact_tab(label, icon_name, stack, page_name)
            if previous is not None:
                button.set_group(previous)
            else:
                first = button
            previous = button
            tabs.append(button)
        if first is not None:
            first.set_active(True)

        body.append(tabs)
        body.append(stack)
        body.append(_footer(self._cancel, tr("Save"), self._save))
        self.win.connect("close-request", self._close)
        self.win.present()

    def _general(self) -> Gtk.Widget:
        behavior = self._group(_t("Proxy behavior"))
        self.autostart = self._switch_row(tr("Start At Login"), autostart_enabled())
        self.show_mode = self._switch_row(
            tr("Show Running Proxy Mode In Status Bar"), self.config.show_mode_in_status_bar
        )
        self.gfw_enabled = self._switch_row(tr("Use GFWList"), self.config.gfwlist_enabled)
        behavior.add(self.autostart)
        behavior.add(self.show_mode)
        behavior.add(self.gfw_enabled)

        gfw = self._group("GFWList")
        self.gfw_url = self._entry_row("GFW List URL", self.config.gfwlist_url)
        gfw.add(self.gfw_url)
        return self._page(behavior, gfw)

    def _advanced(self) -> Gtk.Widget:
        socks = self._group("SOCKS5")
        self.socks_addr = self._entry_row(tr("Local Socks5 Listen Address:"), self.config.socks_listen_address)
        self.socks_port = self._spin_row(tr("Local Socks5 Listen Port:"), self.config.profile.local_port, 1024)
        self.timeout = self._spin_row(tr("Timeout:"), self.config.socks_timeout, 1, 3600)
        self.udp = self._switch_row(tr("Enable Udp Replay"), self.config.udp_relay)
        self.verbose = self._switch_row(tr("Enable Verbose Mode"), self.config.verbose_mode)
        for row in (self.socks_addr, self.socks_port, self.timeout, self.udp, self.verbose):
            socks.add(row)

        pac = self._group(_t("PAC service"))
        self.pac_local = self._switch_row(tr("Local PAC Server Bind To Localhost"), self.config.pac_bind_localhost)
        self.pac_port = self._spin_row(tr("Local PAC Server Listen Port:"), self.config.pac_port, 1024)
        self.external_url = self._entry_row(tr("External PAC URL:"), self.config.external_pac_url)
        for row in (self.pac_local, self.pac_port, self.external_url):
            pac.add(row)
        return self._page(socks, pac)

    def _http(self) -> Gtk.Widget:
        group = self._group(_t("HTTP service"))
        self.http_enabled = self._switch_row(tr("HTTP Proxy Enable"), self.config.http_enabled)
        self.http_addr = self._entry_row(tr("HTTP Proxy Listen Address:"), self.config.http_listen_address)
        self.http_port = self._spin_row(tr("HTTP Proxy Listen Port:"), self.config.http_port, 1024)
        self.abp_url = self._entry_row(tr("ABP PAC engine URL"), self.config.abp_template_url)
        for row in (self.http_enabled, self.http_addr, self.http_port, self.abp_url):
            group.add(row)
        return self._page(group)

    def _network(self) -> Gtk.Widget:
        group = self._group(_t("Network exceptions"))
        self.exceptions = self._entry_row(
            tr("Bypass proxy settings for these Hosts & Domains:"), self.config.proxy_exceptions
        )
        group.add(self.exceptions)
        group.set_description(_t("Separate multiple hosts, domains, or networks with commas."))
        return self._page(group)

    def _save(self, *_args) -> None:
        try:
            external = self.external_url.get_text().strip()
            if external:
                parsed = urlparse(external)
                if parsed.scheme not in ("http", "https") or not parsed.netloc:
                    raise ValueError(tr("External PAC URL must be a valid HTTP or HTTPS URL."))
            socks = int(self.socks_port.get_value())
            pac = int(self.pac_port.get_value())
            http = int(self.http_port.get_value())
            if len({socks, pac, http}) != 3:
                raise ValueError(_t("SOCKS5, PAC and HTTP proxy ports must be different."))
            c = self.config
            c.autostart = self.autostart.get_active()
            c.show_mode_in_status_bar = self.show_mode.get_active()
            c.gfwlist_enabled = self.gfw_enabled.get_active()
            c.gfwlist_url = self.gfw_url.get_text().strip()
            c.socks_listen_address = self.socks_addr.get_text().strip() or "127.0.0.1"
            c.profile.local_port = socks
            c.pac_bind_localhost = self.pac_local.get_active()
            c.pac_port = pac
            c.socks_timeout = int(self.timeout.get_value())
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
        wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=CONTROL_GAP)
        wrap.set_margin_top(PAGE_PAD)
        wrap.set_margin_start(PAGE_PAD)
        wrap.set_margin_end(PAGE_PAD)
        wrap.set_vexpand(True)
        body.append(wrap)
        hint = Gtk.Label(
            label=tr("One rule per line. Adblock/GFWList syntax is supported; @@ rules are DIRECT."),
            xalign=0,
            wrap=True,
        )
        hint.add_css_class("dim-label")
        wrap.append(hint)
        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        self.text = Gtk.TextView(monospace=True)
        self.text.set_top_margin(12)
        self.text.set_bottom_margin(12)
        self.text.set_left_margin(12)
        self.text.set_right_margin(12)
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
        scroller.set_margin_top(PAGE_PAD)
        scroller.set_margin_start(PAGE_PAD)
        scroller.set_margin_end(PAGE_PAD)
        self.text = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
        self.text.set_top_margin(12)
        self.text.set_bottom_margin(12)
        self.text.set_left_margin(12)
        self.text.set_right_margin(12)
        scroller.set_child(self.text)
        body.append(scroller)
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        footer.set_halign(Gtk.Align.END)
        footer.set_margin_top(18)
        footer.set_margin_bottom(ACTION_BOTTOM)
        footer.set_margin_start(PAGE_PAD)
        footer.set_margin_end(PAGE_PAD)
        footer.append(_button(tr("Clear"), self._clear))
        footer.append(_button(tr("Close"), lambda *_: self.quit(), suggested=True))
        body.append(footer)
        self._refresh()
        self.win.present()

    def _refresh(self) -> None:
        try:
            value = (
                LOG_FILE.read_text(encoding="utf-8", errors="replace")
                if LOG_FILE.exists()
                else tr("No proxy log entries yet.")
            )
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
        scroller.set_margin_top(PAGE_PAD)
        scroller.set_margin_start(PAGE_PAD)
        scroller.set_margin_end(PAGE_PAD)
        text = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
        text.set_top_margin(12)
        text.set_bottom_margin(12)
        text.set_left_margin(12)
        text.set_right_margin(12)
        text.get_buffer().set_text(self.value)
        scroller.set_child(text)
        body.append(scroller)
        body.append(_single_footer(tr("Close"), lambda *_: self.quit()))
        win.present()


class ShareApp(Adw.Application):
    def __init__(self, name: str, url: str, qr_path: str = "") -> None:
        super().__init__(application_id=APP_ID + ".Share")
        self.name = name
        self.url = url
        self.qr_path = qr_path

    def do_activate(self) -> None:
        win, _toolbar, body = _window(self, tr("Share Server Configuration…"), 500, 560)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(PAGE_PAD)
        content.set_margin_start(PAGE_PAD)
        content.set_margin_end(PAGE_PAD)
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
        entry.set_hexpand(True)
        content.append(entry)
        body.append(content)
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        footer.set_halign(Gtk.Align.END)
        footer.set_margin_top(18)
        footer.set_margin_bottom(ACTION_BOTTOM)
        footer.set_margin_start(PAGE_PAD)
        footer.set_margin_end(PAGE_PAD)
        footer.append(_button(tr("Close"), lambda *_: self.quit()))
        footer.append(_button(_t("Copy URL"), self._copy, suggested=True))
        body.append(footer)
        self.win = win
        win.present()

    def _copy(self, *_args) -> None:
        self.win.get_clipboard().set(self.url)


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
