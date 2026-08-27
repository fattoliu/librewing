from __future__ import annotations

import copy
import shutil
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from .config import AppConfig, ServerProfile
from .i18n import tr


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

    def do_activate(self) -> None:
        window = Adw.ApplicationWindow(application=self)
        window.set_title(tr("Server Settings"))
        window.set_default_size(860, 560)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(Gtk.Label(label=tr("Server Settings")))
        toolbar.add_top_bar(header)
        window.set_content(toolbar)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        toolbar.set_content(outer)

        paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        paned.set_wide_handle(True)
        paned.set_hexpand(True)
        paned.set_vexpand(True)
        outer.append(paned)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        left.set_margin_top(18)
        left.set_margin_bottom(12)
        left.set_margin_start(18)
        left.set_margin_end(12)
        left.set_size_request(260, -1)
        paned.set_start_child(left)

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
        add.set_tooltip_text(tr("Add server"))
        add.connect("clicked", self._on_add)
        remove = Gtk.Button(icon_name="list-remove-symbolic")
        remove.set_tooltip_text(tr("Remove selected server"))
        remove.connect("clicked", self._on_remove)
        controls.append(add)
        controls.append(remove)
        left.append(controls)

        form_scroll = Gtk.ScrolledWindow()
        form_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        paned.set_end_child(form_scroll)

        clamp = Adw.Clamp(maximum_size=620, tightening_threshold=520)
        clamp.set_margin_top(18)
        clamp.set_margin_bottom(18)
        clamp.set_margin_start(24)
        clamp.set_margin_end(24)
        form_scroll.set_child(clamp)

        form = Gtk.Grid(column_spacing=16, row_spacing=14)
        form.set_hexpand(True)
        clamp.set_child(form)

        self.name = Gtk.Entry()
        self.server = Gtk.Entry()
        self.server_port = Gtk.SpinButton.new_with_range(1, 65535, 1)
        self.password = Gtk.PasswordEntry()
        self.password.set_show_peek_icon(True)
        self.cipher = Gtk.Entry()
        self.plugin = Gtk.Entry()
        self.plugin.set_placeholder_text("/usr/local/bin/obfs-local")
        self.plugin_opts = Gtk.Entry()
        self.plugin_opts.set_placeholder_text("obfs=tls")
        self.local_port = Gtk.SpinButton.new_with_range(1, 65535, 1)

        fields = [
            ("Name", self.name),
            ("Server", self.server),
            ("Server port", self.server_port),
            ("Password", self.password),
            ("Cipher", self.cipher),
            ("Plugin", self.plugin),
            ("Plugin options", self.plugin_opts),
            ("Local SOCKS port", self.local_port),
        ]
        for row, (label, widget) in enumerate(fields):
            caption = Gtk.Label(label=tr(label), halign=Gtk.Align.END, valign=Gtk.Align.CENTER)
            form.attach(caption, 0, row, 1, 1)
            widget.set_hexpand(True)
            form.attach(widget, 1, row, 1, 1)

        note = Gtk.Label(
            label=tr("Tip: select a server on the left to edit it. Add or remove multiple profiles before saving."),
            halign=Gtk.Align.START,
            wrap=True,
            xalign=0,
        )
        note.add_css_class("dim-label")
        form.attach(note, 0, len(fields), 2, 1)

        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        footer.set_halign(Gtk.Align.END)
        footer.set_margin_top(12)
        footer.set_margin_bottom(16)
        footer.set_margin_start(18)
        footer.set_margin_end(18)
        cancel = Gtk.Button(label=tr("Cancel"))
        cancel.connect("clicked", self._on_cancel)
        save = Gtk.Button(label=tr("Save"))
        save.add_css_class("suggested-action")
        save.connect("clicked", self._on_save)
        footer.append(cancel)
        footer.append(save)
        outer.append(footer)

        for widget in (self.name, self.server, self.password, self.cipher, self.plugin, self.plugin_opts):
            widget.connect("changed", self._on_field_changed)
        self.server_port.connect("value-changed", self._on_field_changed)
        self.local_port.connect("value-changed", self._on_field_changed)

        self._refresh_list()
        window.connect("close-request", self._on_close)
        window.present()

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
        p.server_port = self.server_port.get_value_as_int()
        p.password = self.password.get_text()
        p.method = self.cipher.get_text().strip() or "aes-256-gcm"
        p.plugin = self.plugin.get_text().strip()
        p.plugin_opts = self.plugin_opts.get_text().strip()
        p.local_port = self.local_port.get_value_as_int()
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
            dialog.present(self.get_active_window())
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
