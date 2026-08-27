from __future__ import annotations

import sys

from . import app as legacy_app
from .server_manager import ServerManagerDialog


def _open_server_manager(self, add_new: bool = False) -> None:
    """Open the unified server manager and apply all profile changes at once."""
    dialog = ServerManagerDialog(self.config)
    if add_new:
        dialog._on_add(None)
    response = dialog.run()
    if response == legacy_app.Gtk.ResponseType.OK:
        try:
            was_core_running = self.core.running()
            was_http_running = self.http.running()
            dialog.apply()
            if was_core_running:
                self.core.restart()
            if was_http_running:
                self.http.restart()
        except Exception as exc:
            self.alert(f"Failed to save server settings:\n{exc}")
    dialog.destroy()
    self.rebuild_menu()


def _on_add_server(self, _item) -> None:
    _open_server_manager(self, add_new=True)


def _on_edit_server(self, _item) -> None:
    _open_server_manager(self)


def _on_delete_server(self, _item) -> None:
    # Deletion now lives in the unified manager so users can edit/add/remove
    # multiple profiles without bouncing through separate modal dialogs.
    _open_server_manager(self)


def main() -> int:
    # Keep the proven tray/proxy implementation while replacing the old
    # one-profile-at-a-time dialog with the unified ShadowsocksX-NG-style UI.
    legacy_app.TrayApp.on_add_server = _on_add_server
    legacy_app.TrayApp.on_edit_server = _on_edit_server
    legacy_app.TrayApp.on_delete_server = _on_delete_server
    try:
        legacy_app.TrayApp()
        legacy_app.Gtk.main()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"ssx-ng-linux: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
