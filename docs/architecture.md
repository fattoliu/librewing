# Architecture

## Runtime services

`ssxng.launcher` owns the single-instance lock and reclaims only same-user,
orphaned `ss-local` processes launched with this application's exact runtime
configuration path.

The tray process coordinates four services:

1. `ShadowsocksCore` launches and supervises `ss-local`.
2. `HttpProxyCore` converts HTTP proxy and HTTPS CONNECT traffic to SOCKS5.
3. `NgPacServer` serves PAC responses generated from GFWList and user rules.
4. `NgSystemProxy` applies GNOME proxy settings through `gsettings`.

Only item 4 is desktop-specific. Non-GNOME users run Local Proxy Only and configure
applications or their desktop proxy backend themselves. See
[Platform support](platform-support.md) for the maintained boundary.

`RuntimeSupervisor` produces immutable service snapshots and transition events.
It automatically restarts PAC and HTTP services, reports recovery without alert
loops, and disables the GNOME system proxy if `ss-local` or a required PAC
service remains unavailable.

All listeners default to loopback. SOCKS5 and HTTP listeners require explicit
LAN opt-in because they do not authenticate clients.

## User interface

The tray is exported directly through the freedesktop StatusNotifierItem and
DBusMenu protocols using Gio and libdbusmenu. This keeps the familiar Ubuntu
panel workflow without AppIndicator or GTK3. `NgTrayApp` is the explicit
application controller; its windows run as GTK4/libadwaita helpers so a modal
dialog has an isolated toolkit/application lifecycle. Long-running proxy
services remain separate from the UI helpers.

## Persistent state

State lives in `~/.config/librewing`. The directory is mode `0700`;
files containing credentials or operational details are mode `0600` and are
replaced atomically.

`config.json` carries an explicit schema version. Unversioned pre-0.3 files are
migrated in place after a successful parse, while a configuration written by a
newer application version is left byte-for-byte untouched and startup stops
with a clear compatibility error. Corrupt or invalid legacy files are retained
as `config.invalid-*.json` before safe defaults are created.

User-selected backup and server-export destinations receive owner-only files,
but their parent directories are never chmodded by the application.

The stored selected mode is intentionally preserved during normal shutdown,
while the active GNOME system proxy is disabled. This lets the next launch
restore the user's chosen mode without leaving networking dependent on a
stopped process.

## Trust boundaries

- Server URLs, imported JSON, PAC URLs, and QR payloads are untrusted input.
- SIP003 plugins execute as the current user and must resolve to an executable.
- GFWList and PAC templates require HTTPS and content validation.
- Release builds verify bundled binary packages with pinned hashes.
