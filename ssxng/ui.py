from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from .i18n import system_language


_DIALOG_CSS = b"""
/*
 * Important: do NOT style the outer GtkWindow / CSD decoration radius here.
 * Mutter owns the real window surface. Faking a second rounded surface in GTK
 * causes rectangular backing layers to flash while windows are dragged.
 *
 * We only style controls and interior spacing; window corners, shadows and CSD
 * are deliberately left to the GNOME theme/compositor.
 */

.dialog-vbox,
.message-dialog .dialog-vbox {
    padding: 20px 22px 12px 22px;
}

.message-dialog image {
    margin-right: 14px;
}

.message-dialog label {
    font-size: 14px;
}

.dialog-action-area {
    padding: 10px 18px 16px 18px;
    border-top: 1px solid alpha(@theme_fg_color, 0.10);
    background-color: transparent;
}

.dialog-action-area button {
    min-width: 88px;
    min-height: 34px;
    padding: 4px 14px;
    margin-left: 6px;
    border-radius: 8px;
}

.dialog-action-area button.suggested-action,
.dialog-action-area button.destructive-action {
    font-weight: 600;
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

filechooser .dialog-action-area,
.filechooser .dialog-action-area {
    padding-top: 10px;
}

/* Utility classes used by the larger custom dialogs. */
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
    """Install application-wide GTK3 interior dialog styles once."""
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


def polish_dialog(
    dialog: Gtk.Dialog,
    *,
    default_width: int = 480,
    default_height: int = -1,
    resizable: bool = False,
) -> Gtk.Dialog:
    """Apply common geometry, spacing and response styling to any GTK dialog."""
    dialog.set_border_width(0)
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


def _ok_label() -> str:
    language = system_language()
    if language == "zh_CN":
        return "确定"
    if language == "zh_TW":
        return "確定"
    return "OK"


def create_alert(message: str, kind=Gtk.MessageType.INFO, *, parent=None) -> Gtk.MessageDialog:
    """Create the common alert used for latency, status, success and errors."""
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        message_type=kind,
        buttons=Gtk.ButtonsType.OK,
        text=message,
    )
    polish_dialog(dialog, default_width=420)
    try:
        button = dialog.get_widget_for_response(Gtk.ResponseType.OK)
        if button is not None:
            button.set_label(_ok_label())
            button.get_style_context().add_class("suggested-action")
    except Exception:
        pass
    return dialog
