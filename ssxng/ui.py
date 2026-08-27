from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from .i18n import tr


_DIALOG_CSS = b"""
/* Unified dialog surface for normal dialogs, alerts, file choosers and About. */
window.dialog,
window.message-dialog,
window.filechooser,
dialog {
    background-color: @theme_bg_color;
    border-radius: 12px;
}

/* GTK3 can otherwise repaint the bottom action area as a square rectangle.
   Give the whole dialog stack matching lower corner radii. */
window.dialog > box,
window.message-dialog > box,
window.filechooser > box,
.dialog-vbox,
.message-dialog .dialog-vbox {
    border-radius: 12px;
}

.dialog-vbox,
.message-dialog .dialog-vbox {
    padding: 20px 22px 12px 22px;
}

.message-dialog box {
    spacing: 14px;
}

.message-dialog image {
    margin-right: 10px;
}

.message-dialog label {
    font-size: 14px;
}

.dialog-action-area {
    padding: 10px 18px 16px 18px;
    border-top: 1px solid alpha(@theme_fg_color, 0.10);
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
    background-color: @theme_bg_color;
}

.dialog-action-area button {
    min-width: 88px;
    min-height: 34px;
    padding: 4px 14px;
    margin-left: 6px;
    border-radius: 8px;
}

.dialog-action-area button.suggested-action {
    font-weight: 600;
}

.dialog-action-area button.destructive-action {
    font-weight: 600;
}

/* Keep all form-style popups visually consistent. */
entry,
spinbutton,
textview,
combobox button {
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

filechooser .dialog-action-area,
.filechooser .dialog-action-area {
    padding-top: 10px;
}
"""

_provider: Gtk.CssProvider | None = None


def install_dialog_styles() -> None:
    """Install application-wide GTK3 dialog styles once."""
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


def polish_dialog(dialog: Gtk.Dialog, *, default_width: int = 480, resizable: bool = False) -> Gtk.Dialog:
    """Apply consistent geometry, spacing and response styling to a GTK dialog."""
    dialog.set_border_width(0)
    dialog.set_resizable(resizable)
    if default_width > 0:
        dialog.set_default_size(default_width, -1)
    try:
        dialog.set_deletable(True)
        dialog.set_modal(True)
        dialog.set_skip_taskbar_hint(True)
    except Exception:
        pass

    action_area = dialog.get_action_area()
    if action_area is not None:
        action_area.set_spacing(8)

    for response in (Gtk.ResponseType.OK, Gtk.ResponseType.ACCEPT, Gtk.ResponseType.YES, Gtk.ResponseType.APPLY):
        try:
            button = dialog.get_widget_for_response(response)
            if button is not None:
                button.get_style_context().add_class("suggested-action")
        except Exception:
            pass

    for response in (Gtk.ResponseType.REJECT, Gtk.ResponseType.DELETE_EVENT):
        try:
            button = dialog.get_widget_for_response(response)
            if button is not None:
                button.get_style_context().add_class("destructive-action")
        except Exception:
            pass

    try:
        if dialog.get_widget_for_response(Gtk.ResponseType.OK) is not None:
            dialog.set_default_response(Gtk.ResponseType.OK)
    except Exception:
        pass
    return dialog


def create_alert(message: str, kind=Gtk.MessageType.INFO) -> Gtk.MessageDialog:
    """Create the common alert used for latency, status, success and errors."""
    dialog = Gtk.MessageDialog(
        message_type=kind,
        buttons=Gtk.ButtonsType.OK,
        text=message,
    )
    polish_dialog(dialog, default_width=420)
    try:
        button = dialog.get_widget_for_response(Gtk.ResponseType.OK)
        if button is not None:
            button.set_label(tr("OK"))
            button.get_style_context().add_class("suggested-action")
    except Exception:
        pass
    return dialog
