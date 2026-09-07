# Platform support

## Supported baseline

Ubuntu 24.04 and 26.04 with GNOME are the supported desktop targets. Both X11
and Wayland sessions are in scope. Release acceptance requires the manual GNOME
checklist in addition to automated tests.

The Debian packages support amd64 and arm64. Other Ubuntu releases,
architectures, Debian derivatives, and desktop environments are best-effort
unless a release note explicitly promotes them to supported status.

## Desktop feature matrix

| Feature | GNOME on Ubuntu | KDE Plasma, Cinnamon, Xfce, other desktops |
| --- | --- | --- |
| `ss-local`, SIP003 plugins | Supported | Expected to work; desktop-independent |
| Local HTTP proxy and PAC server | Supported | Expected to work; desktop-independent |
| GTK4/libadwaita windows | Supported | Expected to open when GTK4/libadwaita are installed |
| Tray menu | Supported with a StatusNotifierItem watcher | Best-effort; requires a StatusNotifierItem watcher |
| Automatic system proxy | Supported through `org.gnome.system.proxy` | Unsupported; configure the desktop or applications manually |
| Local Proxy Only | Supported | Recommended non-GNOME mode |
| Start at login | Supported | Best-effort through the XDG autostart entry |
| Screen QR scan on Wayland | Supported through the screenshot portal | Best-effort; requires `xdg-desktop-portal` and a working desktop portal backend |
| Screen QR scan on X11 | Supported | Best-effort; requires `gnome-screenshot` or a screenshot portal |

“Expected to work” describes desktop-independent code, not a release-tested
desktop combination. Report the exact distribution, desktop version, session
type, and tray/portal implementation when filing compatibility bugs.

## Non-GNOME operation

Use **Local Proxy Only**. The application keeps SOCKS5, HTTP, and PAC endpoints
running without changing desktop-wide proxy settings. Configure applications
with the local HTTP endpoint shown in Settings, or use **Copy Terminal Proxy
Setup**. A typical shell setup is:

```bash
export http_proxy=http://127.0.0.1:1087
export https_proxy=http://127.0.0.1:1087
```

Smart Routing and All Traffic write GNOME GSettings. On another desktop, those
values are not a supported system-proxy integration and may be ignored. Do not
assume selecting either mode changes every application's proxy settings.

The tray is exported with the freedesktop StatusNotifierItem/DBusMenu
protocols. If no tray icon appears, install or enable the desktop's
StatusNotifier/AppIndicator host. The proxy runtime may still be active; check
it with:

```bash
librewing-tool health
```

## Out of scope

- Desktop-specific proxy backends for KDE, Cinnamon, Xfce, or browsers.
- Transparent routing, TUN mode, firewall changes, and per-application routing.
- Sandboxed Flatpak/Snap integration.
- Mobile platforms, macOS, and Windows.
- Support guarantees for third-party SIP003 plugins.

Contributions adding a desktop backend need isolated integration tests and
must preserve GNOME behavior and Local Proxy Only.
