from __future__ import annotations

from urllib.parse import urlparse

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from .autostart import is_enabled as autostart_enabled
from .config import AppConfig
from .i18n import system_language, tr
from .ui import polish_dialog


_PREF_LABELS = {
    "zh_CN": {
        "General": "常规",
        "Advanced": "高级",
        "Network Interface": "网络接口",
        "Separate multiple hosts, domains, or networks with commas.": "多个主机、域名或网段请使用逗号分隔。",
        "SOCKS5, PAC and HTTP proxy ports must be different.": "SOCKS5、PAC 和 HTTP 代理端口不能相同。",
    },
    "zh_TW": {
        "General": "一般",
        "Advanced": "進階",
        "Network Interface": "網路介面",
        "Separate multiple hosts, domains, or networks with commas.": "多個主機、網域或網段請使用逗號分隔。",
        "SOCKS5, PAC and HTTP proxy ports must be different.": "SOCKS5、PAC 與 HTTP 代理連接埠不能相同。",
    },
}


def _pt(text: str) -> str:
    return _PREF_LABELS.get(system_language(), {}).get(text, tr(text))


def _tab(label: str, icon_name: str) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    image = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
    text = Gtk.Label(label=_pt(label))
    box.pack_start(image, False, False, 0)
    box.pack_start(text, False, False, 0)
    box.show_all()
    return box


def _grid() -> Gtk.Grid:
    return Gtk.Grid(column_spacing=14, row_spacing=12, margin_top=24, margin_bottom=24, margin_start=28, margin_end=28)


def _row(grid: Gtk.Grid, row: int, label: str, widget: Gtk.Widget) -> None:
    grid.attach(Gtk.Label(label=tr(label), halign=Gtk.Align.END), 0, row, 1, 1)
    widget.set_hexpand(True)
    grid.attach(widget, 1, row, 1, 1)


class PreferencesNgDialog(Gtk.Dialog):
    """Single NG-style preferences window with General/Advanced/HTTP/Network panes."""

    def __init__(self, config: AppConfig):
        super().__init__(title=tr("Preferences"), flags=0)
        self.config = config
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        polish_dialog(self, default_width=720, default_height=520, resizable=False)

        notebook = Gtk.Notebook()
        notebook.set_tab_pos(Gtk.PositionType.TOP)
        notebook.set_scrollable(False)
        notebook.set_show_border(False)
        notebook.set_hexpand(True)
        notebook.set_vexpand(True)
        self.get_content_area().add(notebook)

        notebook.append_page(self._general_page(), _tab("General", "preferences-system-symbolic"))
        notebook.append_page(self._advanced_page(), _tab("Advanced", "preferences-other-symbolic"))
        notebook.append_page(self._http_page(), _tab("HTTP", "network-server-symbolic"))
        notebook.append_page(self._network_page(), _tab("Network Interface", "network-workgroup-symbolic"))
        self.show_all()

    def _general_page(self) -> Gtk.Widget:
        grid = _grid()
        self.autostart = Gtk.CheckButton(label=tr("Start At Login"))
        self.autostart.set_active(autostart_enabled())
        grid.attach(self.autostart, 0, 0, 2, 1)

        self.show_mode = Gtk.CheckButton(label=tr("Show Running Proxy Mode In Status Bar"))
        self.show_mode.set_active(self.config.show_mode_in_status_bar)
        grid.attach(self.show_mode, 0, 1, 2, 1)

        self.gfw_enabled = Gtk.CheckButton(label=tr("Use GFWList"))
        self.gfw_enabled.set_active(self.config.gfwlist_enabled)
        grid.attach(self.gfw_enabled, 0, 2, 2, 1)

        self.gfw_url = Gtk.Entry(text=self.config.gfwlist_url)
        _row(grid, 3, "GFW List URL:", self.gfw_url)
        return grid

    def _advanced_page(self) -> Gtk.Widget:
        grid = _grid()
        self.socks_addr = Gtk.Entry(text=self.config.socks_listen_address)
        _row(grid, 0, "Local Socks5 Listen Address:", self.socks_addr)

        self.socks_lan = Gtk.CheckButton(label=tr("Allow SOCKS5 Connections From LAN"))
        self.socks_lan.set_active(self.config.socks_allow_lan)
        grid.attach(self.socks_lan, 0, 1, 2, 1)

        self.socks_port = Gtk.SpinButton.new_with_range(1024, 65535, 1)
        self.socks_port.set_value(self.config.profile.local_port)
        _row(grid, 2, "Local Socks5 Listen Port:", self.socks_port)

        self.pac_local = Gtk.CheckButton(label=tr("Local PAC Server Bind To Localhost"))
        self.pac_local.set_active(self.config.pac_bind_localhost)
        grid.attach(self.pac_local, 0, 3, 2, 1)

        self.pac_port = Gtk.SpinButton.new_with_range(1024, 65535, 1)
        self.pac_port.set_value(self.config.pac_port)
        _row(grid, 4, "Local PAC Server Listen Port:", self.pac_port)

        self.timeout = Gtk.SpinButton.new_with_range(1, 3600, 1)
        self.timeout.set_value(self.config.socks_timeout)
        _row(grid, 5, "Timeout:", self.timeout)

        self.udp = Gtk.CheckButton(label=tr("Enable Udp Replay"))
        self.udp.set_active(self.config.udp_relay)
        grid.attach(self.udp, 0, 6, 2, 1)

        self.verbose = Gtk.CheckButton(label=tr("Enable Verbose Mode"))
        self.verbose.set_active(self.config.verbose_mode)
        grid.attach(self.verbose, 0, 7, 2, 1)

        self.external_url = Gtk.Entry(text=self.config.external_pac_url)
        self.external_url.set_placeholder_text("https://example.com/proxy.pac")
        _row(grid, 8, "External PAC URL:", self.external_url)
        return grid

    def _http_page(self) -> Gtk.Widget:
        grid = _grid()
        self.http_enabled = Gtk.CheckButton(label=tr("HTTP Proxy Enable"))
        self.http_enabled.set_active(self.config.http_enabled)
        grid.attach(self.http_enabled, 0, 0, 2, 1)

        self.http_addr = Gtk.Entry(text=self.config.http_listen_address)
        _row(grid, 1, "HTTP Proxy Listen Address:", self.http_addr)

        self.http_lan = Gtk.CheckButton(label=tr("Allow HTTP Proxy Connections From LAN"))
        self.http_lan.set_active(self.config.http_allow_lan)
        grid.attach(self.http_lan, 0, 2, 2, 1)

        self.http_port = Gtk.SpinButton.new_with_range(1024, 65535, 1)
        self.http_port.set_value(self.config.http_port)
        _row(grid, 3, "HTTP Proxy Listen Port:", self.http_port)

        self.abp_url = Gtk.Entry(text=self.config.abp_template_url)
        _row(grid, 4, "ABP PAC engine URL", self.abp_url)
        return grid

    def _network_page(self) -> Gtk.Widget:
        grid = _grid()
        self.exceptions = Gtk.Entry(text=self.config.proxy_exceptions)
        _row(grid, 0, "Bypass proxy settings for these Hosts & Domains:", self.exceptions)

        help_text = Gtk.Label(label=_pt("Separate multiple hosts, domains, or networks with commas."), halign=Gtk.Align.START, wrap=True)
        help_text.get_style_context().add_class("dim-label")
        grid.attach(help_text, 1, 1, 1, 1)
        return grid

    def apply(self) -> None:
        external = self.external_url.get_text().strip()
        if external:
            parsed = urlparse(external)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(tr("External PAC URL must be a valid HTTP or HTTPS URL."))
        for label, value in (
            ("GFWList URL", self.gfw_url.get_text().strip()),
            ("ABP PAC engine URL", self.abp_url.get_text().strip()),
        ):
            parsed = urlparse(value)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError(tr("{label} must be a valid HTTPS URL.", label=label))

        socks_port = self.socks_port.get_value_as_int()
        pac_port = self.pac_port.get_value_as_int()
        http_port = self.http_port.get_value_as_int()
        if len({socks_port, pac_port, http_port}) != 3:
            raise ValueError(_pt("SOCKS5, PAC and HTTP proxy ports must be different."))

        self.config.autostart = self.autostart.get_active()
        self.config.show_mode_in_status_bar = self.show_mode.get_active()
        self.config.gfwlist_enabled = self.gfw_enabled.get_active()
        self.config.gfwlist_url = self.gfw_url.get_text().strip()

        self.config.socks_listen_address = self.socks_addr.get_text().strip() or "127.0.0.1"
        self.config.socks_allow_lan = self.socks_lan.get_active()
        self.config.profile.local_port = socks_port
        self.config.pac_bind_localhost = self.pac_local.get_active()
        self.config.pac_port = pac_port
        self.config.socks_timeout = self.timeout.get_value_as_int()
        self.config.udp_relay = self.udp.get_active()
        self.config.verbose_mode = self.verbose.get_active()
        self.config.external_pac_url = external

        self.config.http_enabled = self.http_enabled.get_active()
        self.config.http_listen_address = self.http_addr.get_text().strip() or "127.0.0.1"
        self.config.http_allow_lan = self.http_lan.get_active()
        self.config.http_port = http_port
        self.config.abp_template_url = self.abp_url.get_text().strip()
        self.config.proxy_exceptions = self.exceptions.get_text().strip()
        self.config.save()
