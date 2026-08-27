from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Handy", "1")
from gi.repository import Gdk, GLib, Gtk, Handy  # noqa: E402

from .i18n import system_language

Handy.init()

_DIALOG_CSS = b"""
/*
 * GTK3 itself normally leaves the two lower window corners square.  We use
 * libhandy's HdyWindow/HdyHeaderBar for windows that need the modern GNOME
 * silhouette, and keep CSS limited to interior controls.
 */

.ssx-dialog-content {
    padding: 20px 22px 12px 22px;
}

.ssx-dialog-actions {
    padding: 10px 18px 16px 18px;
    border-top: 1px solid alpha(@theme_fg_color, 0.10);
}

.ssx-dialog-actions button {
    min-width: 88px;
    min-height: 34px;
    padding: 4px 14px;
    margin-left: 6px;
    border-radius: 8px;
}

.dialog-vbox,
.message-dialog .dialog-vbox {
    padding: 20px 22px 12px 22px;
}

.dialog-action-area {
    padding: 10px 18px 16px 18px;
    border-top: 1px solid alpha(@theme_fg_color, 0.10);
}

.dialog-action-area button {
    min-width: 88px;
    min-height: 34px;
    padding: 4px 14px;
    margin-left: 6px;
    border-radius: 8px;
}

entry,
spinbutton,
textview,
combobox button,
scrolledwindow,
treeview {
    border-radius: 7px;
}

frame {
    border-radius: 10px;
}

notebook > header {
    padding: 6px 10px;
}

notebook > stack {
    padding: 2px;
}

.ssx-dialog-title {
    font-size: 16px;
    font-weight: 600;
}

.ssx-dialog-subtitle {
    color: alpha(@theme_fg_color, 0.66);
}

.ssx-card {
    background-color: alpha(@theme_fg_color, 0.035);
    border: 1px solid alpha(@theme_fg_color, 0.10);
    border-radius: 10px;
    padding: 14px;
}
"""

_provider: Gtk.CssProvider | None = None


def install_dialog_styles() -> None:
    global _provider
    if _provider is not None:
        return
    screen = Gdk.Screen.get_default()
    if screen is None:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(_DIALOG_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        screen,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    _provider = provider


class HandyDialog(Handy.Window):
    """Small Gtk.Dialog-compatible facade backed by libhandy's HdyWindow.

    GTK3's ordinary GtkDialog has square lower corners.  HdyWindow is the
    supported GTK3-era GNOME solution for rounded lower corners, and avoids the
    fake transparent/ARGB window tricks that caused compositor flicker.
    """

    def __init__(self, *, title: str = "", transient_for=None):
        super().__init__()
        self._response = Gtk.ResponseType.NONE
        self._loop: GLib.MainLoop | None = None
        self._buttons: dict[int, Gtk.Button] = {}

        self.set_title(title)
        self.set_modal(True)
        self.set_skip_taskbar_hint(True)
        self.set_destroy_with_parent(True)
        if transient_for is not None:
            self.set_transient_for(transient_for)

        self._root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(self._root)

        self.headerbar = Handy.HeaderBar()
        self.headerbar.set_title(title)
        self.headerbar.set_show_close_button(True)
        self._root.pack_start(self.headerbar, False, False, 0)

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._content.get_style_context().add_class("ssx-dialog-content")
        self._content.set_hexpand(True)
        self._content.set_vexpand(True)
        self._root.pack_start(self._content, True, True, 0)

        self._actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._actions.set_halign(Gtk.Align.END)
        self._actions.get_style_context().add_class("ssx-dialog-actions")
        self._root.pack_end(self._actions, False, False, 0)

        self.connect("delete-event", self._on_delete)

    def set_title(self, title: str) -> None:
        super().set_title(title)
        if hasattr(self, "headerbar"):
            self.headerbar.set_title(title)

    def get_content_area(self):
        return self._content

    def get_action_area(self):
        return self._actions

    def add_button(self, label: str, response_id: int):
        button = Gtk.Button(label=label)
        button.connect("clicked", lambda _button: self.response(response_id))
        self._actions.pack_start(button, False, False, 0)
        self._buttons[int(response_id)] = button
        return button

    def add_buttons(self, *args) -> None:
        if len(args) % 2:
            raise ValueError("add_buttons expects label/response pairs")
        for index in range(0, len(args), 2):
            self.add_button(str(args[index]), int(args[index + 1]))

    def get_widget_for_response(self, response_id: int):
        return self._buttons.get(int(response_id))

    def set_default_response(self, response_id: int) -> None:
        button = self.get_widget_for_response(response_id)
        if button is not None:
            button.set_can_default(True)
            button.grab_default()

    def response(self, response_id: int) -> None:
        self._response = response_id
        self.hide()
        if self._loop is not None and self._loop.is_running():
            self._loop.quit()

    def _on_delete(self, *_args):
        self.response(Gtk.ResponseType.DELETE_EVENT)
        return True

    def run(self) -> int:
        self._response = Gtk.ResponseType.NONE
        self.show_all()
        self.present()
        self._loop = GLib.MainLoop()
        self._loop.run()
        self._loop = None
        return self._response


def polish_dialog(
    dialog,
    *,
    default_width: int = 480,
    default_height: int = -1,
    resizable: bool = False,
):
    """Apply common geometry, spacing and response styling."""
    try:
        dialog.set_border_width(0)
    except Exception:
        pass
    dialog.set_resizable(resizable)
    if default_width > 0 or default_height > 0:
        dialog.set_default_size(default_width, default_height)
    try:
        dialog.set_deletable(True)
        dialog.set_modal(True)
        dialog.set_skip_taskbar_hint(True)
    except Exception:
        pass

    content = dialog.get_content_area()
    if content is not None:
        content.set_spacing(10)
    action_area = dialog.get_action_area()
    if action_area is not None:
        action_area.set_spacing(8)

    for response in (
        Gtk.ResponseType.OK,
        Gtk.ResponseType.ACCEPT,
        Gtk.ResponseType.YES,
        Gtk.ResponseType.APPLY,
    ):
        button = dialog.get_widget_for_response(response)
        if button is not None:
            button.get_style_context().add_class("suggested-action")

    for response in (Gtk.ResponseType.REJECT, Gtk.ResponseType.DELETE_EVENT):
        button = dialog.get_widget_for_response(response)
        if button is not None:
            button.get_style_context().add_class("destructive-action")

    if dialog.get_widget_for_response(Gtk.ResponseType.OK) is not None:
        dialog.set_default_response(Gtk.ResponseType.OK)
    return dialog


def _ok_label() -> str:
    language = system_language()
    if language == "zh_CN":
        return "确定"
    if language == "zh_TW":
        return "確定"
    return "OK"


def create_alert(message: str, kind=Gtk.MessageType.INFO, *, parent=None):
    """Create a native-looking libhandy alert window."""
    title = "ShadowsocksX-NG Linux"
    dialog = HandyDialog(title=title, transient_for=parent)
    dialog.add_button(_ok_label(), Gtk.ResponseType.OK)
    polish_dialog(dialog, default_width=420)

    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
    row.set_halign(Gtk.Align.FILL)
    row.set_valign(Gtk.Align.CENTER)

    icon_name = {
        Gtk.MessageType.ERROR: "dialog-error-symbolic",
        Gtk.MessageType.WARNING: "dialog-warning-symbolic",
        Gtk.MessageType.QUESTION: "dialog-question-symbolic",
    }.get(kind, "dialog-information-symbolic")
    icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
    icon.set_valign(Gtk.Align.START)
    row.pack_start(icon, False, False, 0)

    label = Gtk.Label(label=message, xalign=0)
    label.set_line_wrap(True)
    label.set_selectable(True)
    label.set_hexpand(True)
    row.pack_start(label, True, True, 0)
    dialog.get_content_area().pack_start(row, True, True, 0)
    return dialog
