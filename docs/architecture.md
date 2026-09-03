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

State lives in `~/.config/shadowsocksx-ng-linux`. The directory is mode `0700`;
files containing credentials or operational details are mode `0600` and are
replaced atomically.

The stored selected mode is intentionally preserved during normal shutdown,
while the active GNOME system proxy is disabled. This lets the next launch
restore the user's chosen mode without leaving networking dependent on a
stopped process.

## Trust boundaries

- Server URLs, imported JSON, PAC URLs, and QR payloads are untrusted input.
- SIP003 plugins execute as the current user and must resolve to an executable.
- GFWList and PAC templates require HTTPS and content validation.
- Release builds verify bundled binary packages with pinned hashes.
