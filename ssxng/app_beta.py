from __future__ import annotations

import signal
import sys

from . import app as legacy_app
from .server_manager import ServerManagerDialog
from .ui import install_dialog_styles


def _open_server_manager(self, add_new: bool = False) -> None:
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
    _open_server_manager(self)


def _shutdown_runtime(self, *, quit_main: bool = True) -> None:
    """Stop runtime services without overwriting the selected proxy mode.

    This method is intentionally idempotent because it is used by the tray Quit
    action, Unix signal handlers, and the final cleanup path in ``main``.
    """
    if getattr(self, "_runtime_shutdown", False):
        if quit_main:
            legacy_app.Gtk.main_quit()
        return
    self._runtime_shutdown = True

    # Quit is not the same as choosing Proxy Off. Disable GNOME's live proxy
    # setting without persisting mode=off so PAC/Global/Manual can be restored
    # automatically on the next launch.
    try:
        self.proxy._gsettings("org.gnome.system.proxy", "mode", "'none'")
    except Exception:
        pass

    # Each stop is isolated so one cleanup failure cannot leave the remaining
    # local services alive.
    for service in (self.http, self.core, self.pac):
        try:
            service.stop()
        except Exception:
            pass

    if quit_main:
        legacy_app.Gtk.main_quit()


def _on_quit(self, _item) -> None:
    self.shutdown_runtime()


def _install_signal_handlers(app) -> None:
    """Route SIGTERM/SIGINT through the same cleanup path as tray Quit."""

    def shutdown_from_signal() -> bool:
        app.shutdown_runtime()
        return False

    # GLib keeps signal handling on the GTK main-loop thread, avoiding direct
    # GTK/process teardown from an asynchronous Python signal handler.
    for signum in (signal.SIGTERM, signal.SIGINT):
        legacy_app.GLib.unix_signal_add(
            legacy_app.GLib.PRIORITY_DEFAULT,
            signum,
            shutdown_from_signal,
        )


def main() -> int:
    # Reuse the proven tray implementation and only replace the server-manager UI.
    # The real HttpProxyCore from app/core must stay enabled so the built-in
    # 127.0.0.1:1087 HTTP-to-SOCKS bridge runs alongside SOCKS and PAC modes.
    legacy_app.TrayApp.on_add_server = _on_add_server
    legacy_app.TrayApp.on_edit_server = _on_edit_server
    legacy_app.TrayApp.on_delete_server = _on_delete_server
    legacy_app.TrayApp.shutdown_runtime = _shutdown_runtime
    legacy_app.TrayApp.on_quit = _on_quit

    app = None
    try:
        install_dialog_styles()
        app = legacy_app.TrayApp()
        _install_signal_handlers(app)
        legacy_app.Gtk.main()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"ssx-ng-linux: {exc}", file=sys.stderr)
        return 1
    finally:
        if app is not None:
            app.shutdown_runtime(quit_main=False)


if __name__ == "__main__":
    raise SystemExit(main())
