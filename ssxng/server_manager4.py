from __future__ import annotations

import copy
import shutil
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from .config import AppConfig, ServerProfile
from .i18n import tr

PAGE_PAD = 24


class ServerSettingsApp(Adw.Application):
    """GTK4/libadwaita server editor, isolated from the GTK3 tray process."""

    def __init__(self) -> None:
        super().__init__(application_id="io.github.fattoliu.shadowsocksxng.ServerSettings")
        self.saved = False
        self.config = AppConfig.load()
        self.profiles = copy.deepcopy(self.config.profiles)
        self.active_index = min(self.config.active_profile, len(self.profiles) - 1)
        self.loading = False
        self.rows: list[Gtk.ListBoxRow] = []

    @staticmethod
    def _button(label: str, callback, *, suggested: bool = False) -> Gtk.Button:
        button = Gtk.Button(label=label)
        if suggested:
            button.add_css_class("suggested-action")
        button.connect("clicked", callback)
        return button

    @staticmethod
    def _entry_row(title: str) -> Adw.EntryRow:
        return Adw.EntryRow(title=title)

    @staticmethod
    def _spin_row(title: str, minimum: int = 1, maximum: int = 65535) -> Adw.SpinRow:
        adjustment = Gtk.Adjustment(value=minimum, lower=minimum, upper=maximum, step_increment=1, page_increment=10)
        return Adw.SpinRow(title=title, adjustment=adjustment)

    def do_activate(self) -> None:
        self.window = Adw.ApplicationWindow(application=self)
        self.window.set_title(tr("Server Settings"))
        self.window.set_default_size(880, 590)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label=tr("Server Settings")))
        toolbar.add_top_bar(header)
        try:
            toolbar.set_top_bar_style(Adw.ToolbarStyle.FLAT)
        except Exception:
            pass
        self.window.set_content(toolbar)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        toolbar.set_content(outer)

        # Deliberately avoid Gtk.Paned here. The old wide handle drew a heavy,
        # full-height divider that made the window look like a prototype.
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=28)
        content.set_margin_top(PAGE_PAD)
        content.set_margin_start(PAGE_PAD)
        content.set_margin_end(PAGE_PAD)
        content.set_vexpand(True)
        outer.append(content)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        left.set_size_request(250, -1)
        content.append(left)

        self.listbox = Gtk.ListBox()
        self.listbox.add_css_class("boxed-list")
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-selected", self._on_row_selected)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self.listbox)
        scroller.set_vexpand(True)
        left.append(scroller)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        add = Gtk.Button(icon_name="list-add-symbolic")
        add.add_css_class("flat")
        add.set_tooltip_text(tr("Add server"))
        add.connect("clicked", self._on_add)
        remove = Gtk.Button(icon_name="list-remove-symbolic")
        remove.add_css_class("flat")
        remove.set_tooltip_text(tr("Remove selected server"))
        remove.connect("clicked", self._on_remove)
        controls.append(add)
        controls.append(remove)
        left.append(controls)

        right_scroll = Gtk.ScrolledWindow()
        right_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        right_scroll.set_hexpand(True)
        right_scroll.set_vexpand(True)
        content.append(right_scroll)

        clamp = Adw.Clamp(maximum_size=620, tightening_threshold=520)
        right_scroll.set_child(clamp)

        form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        form.set_margin_bottom(8)
        clamp.set_child(form)

        group = Adw.PreferencesGroup()
        form.append(group)

        self.name = self._entry_row(tr("Name"))
        self.server = self._entry_row(tr("Server"))
        self.server_port = self._spin_row(tr("Server port"))
        self.password = Adw.PasswordEntryRow(title=tr("Password"))
        self.password.set_show_apply_button(False)
        self.cipher = self._entry_row(tr("Cipher"))
        self.plugin = self._entry_row(tr("Plugin"))
        self.plugin_opts = self._entry_row(tr("Plugin options"))
        self.local_port = self._spin_row(tr("Local SOCKS port"))

        for row in (
            self.name,
            self.server,
            self.server_port,
            self.password,
            self.cipher,
            self.plugin,
            self.plugin_opts,
            self.local_port,
        ):
            group.add(row)

        note = Gtk.Label(
            label=tr("Tip: select a server on the left to edit it. Add or remove multiple profiles before saving."),
            halign=Gtk.Align.START,
            wrap=True,
            xalign=0,
        )
        note.add_css_class("dim-label")
        form.append(note)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        footer.set_halign(Gtk.Align.END)
        footer.set_margin_top(18)
        footer.set_margin_bottom(PAGE_PAD)
        footer.set_margin_start(PAGE_PAD)
        footer.set_margin_end(PAGE_PAD)
        footer.append(self._button(tr("Cancel"), self._on_cancel))
        footer.append(self._button(tr("Save"), self._on_save, suggested=True))
        outer.append(footer)

        for widget in (self.name, self.server, self.password, self.cipher, self.plugin, self.plugin_opts):
            widget.connect("changed", self._on_field_changed)
        self.server_port.connect("notify::value", self._on_field_changed)
        self.local_port.connect("notify::value", self._on_field_changed)

        self._refresh_list()
        self.window.connect("close-request", self._on_close)
        self.window.present()

    def _refresh_list(self) -> None:
        while child := self.listbox.get_first_child():
            self.listbox.remove(child)
        self.rows.clear()
        for profile in self.profiles:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=profile.name or "Default", xalign=0)
            label.set_margin_top(10)
            label.set_margin_bottom(10)
            label.set_margin_start(12)
            label.set_margin_end(12)
            row.set_child(label)
            self.listbox.append(row)
            self.rows.append(row)
        if self.rows:
            self.active_index = max(0, min(self.active_index, len(self.rows) - 1))
            self.listbox.select_row(self.rows[self.active_index])

    def _on_row_selected(self, _box, row) -> None:
        if row is None:
            return
        self.active_index = row.get_index()
        self._load_profile(self.profiles[self.active_index])

    def _load_profile(self, p: ServerProfile) -> None:
        self.loading = True
        try:
            self.name.set_text(p.name)
            self.server.set_text(p.server)
            self.server_port.set_value(p.server_port)
            self.password.set_text(p.password)
            self.cipher.set_text(p.method)
            self.plugin.set_text(p.plugin)
            self.plugin_opts.set_text(p.plugin_opts)
            self.local_port.set_value(p.local_port)
        finally:
            self.loading = False

    def _on_field_changed(self, *_args) -> None:
        if self.loading or not self.profiles:
            return
        p = self.profiles[self.active_index]
        p.name = self.name.get_text().strip() or "Default"
        p.server = self.server.get_text().strip()
        p.server_port = int(self.server_port.get_value())
        p.password = self.password.get_text()
        p.method = self.cipher.get_text().strip() or "aes-256-gcm"
        p.plugin = self.plugin.get_text().strip()
        p.plugin_opts = self.plugin_opts.get_text().strip()
        p.local_port = int(self.local_port.get_value())
        row = self.rows[self.active_index]
        label = row.get_child()
        label.set_text(p.name)

    def _on_add(self, _button) -> None:
        self.profiles.append(
            ServerProfile(name=f"Server {len(self.profiles) + 1}", plugin=shutil.which("obfs-local") or "")
        )
        self.active_index = len(self.profiles) - 1
        self._refresh_list()

    def _on_remove(self, _button) -> None:
        if len(self.profiles) <= 1:
            dialog = Adw.AlertDialog.new(tr("Server Settings"), tr("At least one server profile must remain."))
            dialog.add_response("ok", tr("OK"))
            dialog.present(self.window)
            return
        del self.profiles[self.active_index]
        self.active_index = min(self.active_index, len(self.profiles) - 1)
        self._refresh_list()

    def _on_save(self, _button) -> None:
        self.config.profiles = self.profiles
        self.config.active_profile = max(0, min(self.active_index, len(self.profiles) - 1))
        self.config.save()
        self.saved = True
        self.quit()

    def _on_cancel(self, _button) -> None:
        self.saved = False
        self.quit()

    def _on_close(self, _window) -> bool:
        self.saved = False
        self.quit()
        return False


def main() -> int:
    app = ServerSettingsApp()
    app.run(sys.argv)
    return 0 if app.saved else 2


if __name__ == "__main__":
    raise SystemExit(main())
