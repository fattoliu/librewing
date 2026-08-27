from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402


_DIALOG_CSS = b"""
/* Keep dialog action buttons away from window edges consistently. */
.dialog-action-area {
    padding: 8px 16px 16px 16px;
}

.dialog-action-area button {
    min-width: 72px;
    margin-left: 4px;
}
"""

_provider: Gtk.CssProvider | None = None


def install_dialog_styles() -> None:
    """Install application-wide GTK3 dialog spacing rules once.

    Gtk.Dialog keeps its action area outside the content area, so margins on the
    content widget do not affect the bottom-right buttons. Styling the standard
    ``dialog-action-area`` class fixes every normal dialog, message dialog, and
    about dialog consistently without per-window layout patches.
    """
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
