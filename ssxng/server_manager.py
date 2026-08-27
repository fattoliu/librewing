from __future__ import annotations

import copy
import shutil

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from .config import AppConfig, ServerProfile
from .i18n import tr
from .ui import HandyDialog, create_alert, polish_dialog

CIPHERS = [
    "aes-256-gcm",
    "aes-192-gcm",
    "aes-128-gcm",
    "chacha20-ietf-poly1305",
    "xchacha20-ietf-poly1305",
    "aes-256-cfb",
    "aes-192-cfb",
    "aes-128-cfb",
    "aes-256-ctr",
    "aes-192-ctr",
    "aes-128-ctr",
    "camellia-256-cfb",
    "camellia-192-cfb",
    "camellia-128-cfb",
    "bf-cfb",
]


class ServerManagerDialog(HandyDialog):
    """Manage all Shadowsocks server profiles in one libhandy window."""

    def __init__(self, config: AppConfig):
        super().__init__(title=tr("Server Settings"))
        self.config = config
        self.profiles = copy.deepcopy(config.profiles)
        self.active_index = min(config.active_profile, len(self.profiles) - 1)
        self.loading = False

        # Never use Gtk.STOCK_* IDs here: with modern themes/libhandy they can
        # render literally as "gtk-cancel" / "gtk-save" instead of localized
        # labels. Use our i18n strings explicitly.
        self.add_buttons(tr("Cancel"), Gtk.ResponseType.CANCEL, tr("Save"), Gtk.ResponseType.OK)
        polish_dialog(self, default_width=820, default_height=520, resizable=True)

        content = self.get_content_area()
        content.set_spacing(0)
        content.set_margin_top(22)
        content.set_margin_bottom(18)
        content.set_margin_start(22)
        content.set_margin_end(22)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=22)
        root.set_hexpand(True)
        root.set_vexpand(True)
        content.pack_start(root, True, True, 0)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        left.set_size_request(250, -1)
        root.pack_start(left, False, False, 0)

        self.store = Gtk.ListStore(str)
        self.list_view = Gtk.TreeView(model=self.store)
        self.list_view.set_headers_visible(False)
        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", 3)
        self.list_view.append_column(Gtk.TreeViewColumn(tr("Server"), renderer, text=0))
        self.list_view.get_selection().connect("changed", self._on_selection_changed)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_shadow_type(Gtk.ShadowType.IN)
        scroller.add(self.list_view)
        left.pack_start(scroller, True, True, 0)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        add = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON)
        add.set_tooltip_text(tr("Add server"))
        add.connect("clicked", self._on_add)
        remove = Gtk.Button.new_from_icon_name("list-remove-symbolic", Gtk.IconSize.BUTTON)
        remove.set_tooltip_text(tr("Remove selected server"))
        remove.connect("clicked", self._on_remove)
        controls.pack_start(add, False, False, 0)
        controls.pack_start(remove, False, False, 0)
        left.pack_start(controls, False, False, 0)

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        root.pack_start(separator, False, False, 0)

        form = Gtk.Grid(column_spacing=16, row_spacing=14)
        form.set_hexpand(True)
        form.set_valign(Gtk.Align.START)
        root.pack_start(form, True, True, 0)

        self.name = self._entry()
        self.server = self._entry()
        self.server_port = Gtk.SpinButton.new_with_range(1, 65535, 1)
        self.password = self._entry()
        self.password.set_visibility(False)
        self.password.set_invisible_char("•")
        self.cipher = Gtk.ComboBoxText.new_with_entry()
        for method in CIPHERS:
            self.cipher.append_text(method)
        self.plugin = self._entry()
        self.plugin.set_placeholder_text("e.g. /usr/local/bin/obfs-local")
        self.plugin_opts = self._entry()
        self.plugin_opts.set_placeholder_text("e.g. obfs=tls")
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
            form.attach(Gtk.Label(label=tr(label), halign=Gtk.Align.END, valign=Gtk.Align.CENTER), 0, row, 1, 1)
            widget.set_hexpand(True)
            form.attach(widget, 1, row, 1, 1)

        note = Gtk.Label(
            label=tr("Tip: select a server on the left to edit it. Add or remove multiple profiles before saving."),
            halign=Gtk.Align.START,
            wrap=True,
        )
        note.get_style_context().add_class("dim-label")
        form.attach(note, 0, len(fields), 2, 1)

        for widget in (self.name, self.server, self.password, self.plugin, self.plugin_opts):
            widget.connect("changed", self._on_field_changed)
        self.server_port.connect("value-changed", self._on_field_changed)
        self.local_port.connect("value-changed", self._on_field_changed)
        self.cipher.connect("changed", self._on_field_changed)

        self._refresh_list(select=self.active_index)
        self.show_all()

    @staticmethod
    def _entry() -> Gtk.Entry:
        entry = Gtk.Entry()
        entry.set_width_chars(38)
        return entry

    def _refresh_list(self, select: int | None = None) -> None:
        self.store.clear()
        for p in self.profiles:
            self.store.append([p.name or "Default"])
        if select is not None and self.profiles:
            path = Gtk.TreePath.new_from_indices([max(0, min(select, len(self.profiles) - 1))])
            self.list_view.get_selection().select_path(path)
            self.list_view.scroll_to_cell(path, None, False, 0, 0)

    def _selected_index(self) -> int:
        model, tree_iter = self.list_view.get_selection().get_selected()
        if tree_iter is None:
            return 0
        path = model.get_path(tree_iter)
        return path.get_indices()[0]

    def _on_selection_changed(self, _selection) -> None:
        if not self.profiles:
            return
        self.active_index = self._selected_index()
        self._load_profile(self.profiles[self.active_index])

    def _load_profile(self, profile: ServerProfile) -> None:
        self.loading = True
        try:
            self.name.set_text(profile.name)
            self.server.set_text(profile.server)
            self.server_port.set_value(profile.server_port)
            self.password.set_text(profile.password)
            entry = self.cipher.get_child()
            entry.set_text(profile.method)
            self.plugin.set_text(profile.plugin)
            self.plugin_opts.set_text(profile.plugin_opts)
            self.local_port.set_value(profile.local_port)
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
        p.method = self.cipher.get_child().get_text().strip() or "aes-256-gcm"
        p.plugin = self.plugin.get_text().strip()
        p.plugin_opts = self.plugin_opts.get_text().strip()
        p.local_port = self.local_port.get_value_as_int()
        tree_iter = self.store.iter_nth_child(None, self.active_index)
        if tree_iter is not None:
            self.store.set_value(tree_iter, 0, p.name)

    def _on_add(self, _button) -> None:
        profile = ServerProfile(
            name=f"Server {len(self.profiles) + 1}",
            plugin=shutil.which("obfs-local") or "",
        )
        self.profiles.append(profile)
        self.active_index = len(self.profiles) - 1
        self._refresh_list(select=self.active_index)

    def _on_remove(self, _button) -> None:
        if len(self.profiles) <= 1:
            message = create_alert(
                tr("At least one server profile must remain."),
                Gtk.MessageType.INFO,
                parent=self,
            )
            message.run()
            message.destroy()
            return
        index = self._selected_index()
        del self.profiles[index]
        self.active_index = min(index, len(self.profiles) - 1)
        self._refresh_list(select=self.active_index)

    def apply(self) -> None:
        if not self.profiles:
            raise ValueError(tr("At least one server profile must remain."))
        self.config.profiles = self.profiles
        self.config.active_profile = max(0, min(self.active_index, len(self.profiles) - 1))
        self.config.save()