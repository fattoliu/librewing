from __future__ import annotations

from urllib.parse import urlparse

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from .config import AppConfig
from .i18n import tr


def _row(grid: Gtk.Grid, row: int, label: str, widget: Gtk.Widget) -> None:
    grid.attach(Gtk.Label(label=tr(label), halign=Gtk.Align.START), 0, row, 1, 1)
    grid.attach(widget, 1, row, 1, 1)


class AdvancedPreferencesDialog(Gtk.Dialog):
    """Linux equivalent of NG's Advanced + HTTP preference panes."""

    def __init__(self, config: AppConfig):
        super().__init__(title=tr("Advanced Preferences…"), flags=0)
        self.config = config
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        self.set_default_size(600, 470)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, margin=18)
        self.get_content_area().add(box)

        socks_frame = Gtk.Frame(label=tr("SOCKS5"))
        socks_grid = Gtk.Grid(column_spacing=14, row_spacing=10, margin=14)
        socks_frame.add(socks_grid)
        box.pack_start(socks_frame, False, False, 0)

        self.socks_addr = Gtk.Entry(text=config.socks_listen_address)
        _row(socks_grid, 0, "Local Socks5 Listen Address:", self.socks_addr)

        self.socks_port = Gtk.SpinButton.new_with_range(1024, 65535, 1)
        self.socks_port.set_value(config.profile.local_port)
        _row(socks_grid, 1, "Local Socks5 Listen Port:", self.socks_port)

        self.timeout = Gtk.SpinButton.new_with_range(1, 3600, 1)
        self.timeout.set_value(config.socks_timeout)
        _row(socks_grid, 2, "Timeout:", self.timeout)

        self.udp = Gtk.CheckButton(label=tr("Enable Udp Replay"))
        self.udp.set_active(config.udp_relay)
        socks_grid.attach(self.udp, 0, 3, 2, 1)

        self.verbose = Gtk.CheckButton(label=tr("Enable Verbose Mode"))
        self.verbose.set_active(config.verbose_mode)
        socks_grid.attach(self.verbose, 0, 4, 2, 1)

        http_frame = Gtk.Frame(label="HTTP")
        http_grid = Gtk.Grid(column_spacing=14, row_spacing=10, margin=14)
        http_frame.add(http_grid)
        box.pack_start(http_frame, False, False, 0)

        self.http_enabled = Gtk.CheckButton(label=tr("HTTP Proxy Enable"))
        self.http_enabled.set_active(config.http_enabled)
        http_grid.attach(self.http_enabled, 0, 0, 2, 1)

        self.http_addr = Gtk.Entry(text=config.http_listen_address)
        _row(http_grid, 1, "HTTP Proxy Listen Address:", self.http_addr)

        self.http_port = Gtk.SpinButton.new_with_range(1024, 65535, 1)
        self.http_port.set_value(config.http_port)
        _row(http_grid, 2, "HTTP Proxy Listen Port:", self.http_port)

        self.show_mode = Gtk.CheckButton(label=tr("Show Running Proxy Mode In Status Bar"))
        self.show_mode.set_active(config.show_mode_in_status_bar)
        box.pack_start(self.show_mode, False, False, 0)
        self.show_all()

    def apply(self) -> None:
        socks_addr = self.socks_addr.get_text().strip() or "127.0.0.1"
        http_addr = self.http_addr.get_text().strip() or "127.0.0.1"
        self.config.socks_listen_address = socks_addr
        self.config.profile.local_port = self.socks_port.get_value_as_int()
        self.config.socks_timeout = self.timeout.get_value_as_int()
        self.config.udp_relay = self.udp.get_active()
        self.config.verbose_mode = self.verbose.get_active()
        self.config.http_enabled = self.http_enabled.get_active()
        self.config.http_listen_address = http_addr
        self.config.http_port = self.http_port.get_value_as_int()
        self.config.show_mode_in_status_bar = self.show_mode.get_active()
        self.config.save()


class AdvancedPacDialog(Gtk.Dialog):
    """NG-compatible local/external PAC settings."""

    def __init__(self, config: AppConfig):
        super().__init__(title=tr("Advanced PAC Proxy Preferences…"), flags=0)
        self.config = config
        self.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        self.set_default_size(680, 390)

        grid = Gtk.Grid(column_spacing=14, row_spacing=12, margin=18)
        self.get_content_area().add(grid)

        self.bind_local = Gtk.CheckButton(label=tr("Local PAC Server Bind To Localhost"))
        self.bind_local.set_active(config.pac_bind_localhost)
        grid.attach(self.bind_local, 0, 0, 2, 1)

        self.pac_port = Gtk.SpinButton.new_with_range(1024, 65535, 1)
        self.pac_port.set_value(config.pac_port)
        _row(grid, 1, "Local PAC Server Listen Port:", self.pac_port)

        self.gfw_url = Gtk.Entry(text=config.gfwlist_url)
        self.gfw_url.set_hexpand(True)
        _row(grid, 2, "GFW List URL:", self.gfw_url)

        self.external_url = Gtk.Entry(text=config.external_pac_url)
        self.external_url.set_hexpand(True)
        self.external_url.set_placeholder_text("https://example.com/proxy.pac")
        _row(grid, 3, "External PAC URL:", self.external_url)

        self.exceptions = Gtk.Entry(text=config.proxy_exceptions)
        self.exceptions.set_hexpand(True)
        _row(grid, 4, "Bypass proxy settings for these Hosts & Domains:", self.exceptions)

        info = Gtk.Label(
            label=tr("External PAC mode becomes available after a valid HTTP/HTTPS PAC URL is saved."),
            halign=Gtk.Align.START,
            wrap=True,
        )
        grid.attach(info, 0, 5, 2, 1)
        self.show_all()

    def apply(self) -> None:
        external = self.external_url.get_text().strip()
        if external:
            parsed = urlparse(external)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(tr("External PAC URL must be a valid HTTP or HTTPS URL."))
        self.config.pac_bind_localhost = self.bind_local.get_active()
        self.config.pac_port = self.pac_port.get_value_as_int()
        self.config.gfwlist_url = self.gfw_url.get_text().strip()
        self.config.external_pac_url = external
        self.config.proxy_exceptions = self.exceptions.get_text().strip()
        self.config.save()
