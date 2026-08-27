from __future__ import annotations

import sys

from . import app as legacy_app
from . import pac as pac_module
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


_original_build_pac = pac_module.build_pac


def _build_native_socks_pac(config):
    """Keep the existing GFWList/ABP engine but route matches to SOCKS directly."""
    pac = _original_build_pac(config)
    old = f"PROXY 127.0.0.1:{config.http_port}"
    new = (
        f"SOCKS5 127.0.0.1:{config.profile.local_port}; "
        f"SOCKS 127.0.0.1:{config.profile.local_port}"
    )
    return pac.replace(old, new)


def _global_mode_native_socks(self) -> None:
    """Match ShadowsocksX-NG more closely by exposing the local SOCKS proxy directly."""
    self._gsettings("org.gnome.system.proxy", "mode", "'manual'")
    self._gsettings("org.gnome.system.proxy", "use-same-proxy", "false")

    # Clear stale HTTP/HTTPS proxy values from older Privoxy-based builds.
    for schema in ("org.gnome.system.proxy.http", "org.gnome.system.proxy.https"):
        self._gsettings(schema, "host", "''")
        self._gsettings(schema, "port", "0")

    self._gsettings("org.gnome.system.proxy.socks", "host", "'127.0.0.1'")
    self._gsettings("org.gnome.system.proxy.socks", "port", str(self.config.profile.local_port))
    self.config.mode = "global"
    self.config.save()


def _open_server_manager(self, add_new: bool = False) -> None:
    """Open the unified server manager and apply all profile changes at once."""
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
    # Native SOCKS is both simpler and closer to ShadowsocksX-NG. Privoxy is no
    # longer started by the desktop client; PAC rules return SOCKS5/SOCKS directly.
    legacy_app.HttpProxyCore = _NativeSocksHttpProxyCore
    legacy_app.SystemProxy.global_mode = _global_mode_native_socks
    pac_module.build_pac = _build_native_socks_pac

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
