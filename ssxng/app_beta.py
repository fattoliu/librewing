from __future__ import annotations

import sys

from . import app as legacy_app
from .server_manager import ServerManagerDialog


class _NativeSocksHttpProxyCore:
    """Compatibility shim: native SOCKS modes no longer need Privoxy."""

    def __init__(self, config):
        self.config = config

    def start(self) -> None:
        return

    def stop(self) -> None:
        return

    def restart(self) -> None:
        return

    def running(self) -> bool:
        return False


def _open_server_manager(self, add_new: bool = False) -> None:
    dialog = ServerManagerDialog(self.config)
    if add_new:
        dialog._on_add(None)
    response = dialog.run()
    if response == legacy_app.Gtk.ResponseType.OK:
        try:
            was_core_running = self.core.running()
            dialog.apply()
            if was_core_running:
                self.core.restart()
        except Exception as exc:
            self.alert(f"Failed to save server settings:\n{exc}")
    dialog.destroy()
    self.rebuild_menu()


def _on_add_server(self, _item) -> None:
    _open_server_manager(self, add_new=True)


def _on_edit_server(self, _item) -> None:
    _open_server_manager(self)


def _on_delete_server(self, _item) -> None:
    _open_server_manager(self)


def main() -> int:
    # Keep the proven tray implementation, but disable the legacy Privoxy layer.
    # SystemProxy and PacServer now implement both PAC and Global modes directly
    # using explicit SOCKS5 PAC results.
    legacy_app.HttpProxyCore = _NativeSocksHttpProxyCore

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
