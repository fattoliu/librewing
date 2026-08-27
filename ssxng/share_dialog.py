from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from gi.repository import GdkPixbuf

from . import app as legacy_app
from .i18n import tr
from .share import build_ss_url
from .ui import polish_dialog


class ShareServerDialog(legacy_app.Gtk.Dialog):
    """Show the active server URL and QR code in the common dialog style."""

    RESPONSE_COPY = 1001

    def __init__(self, profile):
        super().__init__(title=tr("Share Server Configuration…"), flags=0)
        self.profile = profile
        self.url = build_ss_url(profile)
        self.add_buttons(
            tr("Copy URL"),
            self.RESPONSE_COPY,
            legacy_app.Gtk.STOCK_CLOSE,
            legacy_app.Gtk.ResponseType.CLOSE,
        )
        polish_dialog(self, default_width=480, default_height=520, resizable=False)

        box = legacy_app.Gtk.Box(
            orientation=legacy_app.Gtk.Orientation.VERTICAL,
            spacing=14,
            margin=22,
        )
        self.get_content_area().add(box)

        title = legacy_app.Gtk.Label()
        title.set_markup(f"<b>{legacy_app.GLib.markup_escape_text(profile.name)}</b>")
        title.get_style_context().add_class("ssx-dialog-title")
        box.pack_start(title, False, False, 0)

        qr = self._qr_image()
        if qr is not None:
            box.pack_start(qr, True, True, 0)

        url_label = legacy_app.Gtk.Label(label=self.url)
        url_label.set_selectable(True)
        url_label.set_line_wrap(True)
        url_label.set_max_width_chars(58)
        url_label.get_style_context().add_class("ssx-dialog-subtitle")
        box.pack_start(url_label, False, False, 0)
        self.show_all()

    def _qr_image(self):
        qrencode = shutil.which("qrencode")
        if not qrencode:
            return None
        with tempfile.TemporaryDirectory(prefix="ssxng-share-") as tmp:
            path = Path(tmp) / "server.png"
            result = subprocess.run(
                [qrencode, "-s", "7", "-m", "2", "-o", str(path), self.url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
            if result.returncode != 0 or not path.exists():
                return None
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(path))
            return legacy_app.Gtk.Image.new_from_pixbuf(pixbuf)

    def copy_url(self) -> None:
        clipboard = legacy_app.Gtk.Clipboard.get(legacy_app.Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(self.url, -1)
        clipboard.store()
