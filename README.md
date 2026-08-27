# ShadowsocksX-NG Linux

A Linux/Ubuntu desktop client inspired by [ShadowsocksX-NG](https://github.com/shadowsocks/ShadowsocksX-NG), with a tray-first workflow and GNOME integration.

The project keeps the familiar ShadowsocksX-NG concepts—external `ss-local`, SIP003 plugins, PAC/GFWList rules, server profiles and menu-bar style control—while replacing macOS-only APIs with Linux/GNOME equivalents.

## Current feature set

- Ayatana AppIndicator tray UI with upstream ShadowsocksX-NG paper-plane status icons
- PAC / Global / Manual / External PAC modes
- Automatic mode indicator (`P`, `G`, `M`) in the status bar
- Multiple Shadowsocks server profiles and profile switching
- Server settings window with SIP003 plugin/plugin options
- `ss://` URL import, clipboard import, QR scan and QR sharing
- Server TCP latency test
- External `ss-local` lifecycle management and orphan-process recovery
- Native local HTTP → SOCKS5 bridge for terminal/application proxy use
- Local PAC server with GFWList and custom user rules
- Background GFWList update with cached last-known-good data
- GNOME system proxy integration
- Unified NG-style Preferences window: General / Advanced / HTTP / Network Interface
- Start-at-login integration
- Localized UI following the system locale (Simplified Chinese, Traditional Chinese, English fallback)
- Logs, diagnostics export, update/help links
- Offline `.deb` package build; tray icon resources are vendored in the repository
- Health-check CLI via `ssx-ng-tool health`
- GitHub Actions unit, desktop-import and Debian-package smoke tests

## Architecture

```text
GNOME / Ubuntu tray
        │
        ├── Preferences / server profiles / PAC rules
        ├── QR import & sharing / latency / logs
        └── proxy mode
              │
              ├── Off          → GNOME proxy disabled
              ├── Manual       → local proxies kept available; system proxy disabled
              ├── PAC          → GNOME auto proxy → local /proxy.pac
              ├── Global       → GNOME auto proxy → local /global.pac
              └── External PAC → GNOME auto proxy → configured external PAC URL
                                      │
                         local HTTP bridge / SOCKS5
                                      │
                                  ss-local
                                      │
                              SIP003 plugin
                           (e.g. simple-obfs)
                                      │
                              Shadowsocks server
```

The HTTP bridge exists because terminal tools and many Linux desktop applications consistently support `http_proxy` / `https_proxy`, while `ss-local` itself exposes SOCKS5.

## Ubuntu install

```bash
git clone https://github.com/fattoliu/shadowsocksx-ng-linux.git
cd shadowsocksx-ng-linux
git checkout dev/mvp
bash scripts/install-ubuntu.sh
```

Run the installed native package entrypoint:

```bash
ssx-ng-linux
```

Useful diagnostics:

```bash
ssx-ng-tool health
```

The Debian package installs the desktop client into `/usr/bin` and its Python modules under `/usr/lib/shadowsocksx-ng-linux`.

If the selected server uses `simple-obfs`, install `obfs-local` separately and configure the server profile, for example:

```text
Plugin: /usr/local/bin/obfs-local
Plugin options: obfs=tls
```

## Terminal proxy

The desktop client's local HTTP proxy defaults to `127.0.0.1:1087`. A shell can opt in with environment variables:

```bash
export http_proxy=http://127.0.0.1:1087
export https_proxy=http://127.0.0.1:1087
```

The tray menu also provides **Copy Terminal Proxy Command**.

## Modes

### PAC Auto Mode

The local PAC server uses GFWList plus user rules to decide whether a destination should use Shadowsocks or connect directly.

### Global Mode

The local global PAC endpoint sends all normal traffic through the local proxy bridge. Using a PAC endpoint also avoids inconsistent SOCKS-only handling across GNOME applications.

### Manual Mode

`ss-local` and enabled local proxy services remain available, but GNOME system proxy settings are disabled. Applications can opt in manually.

### External PAC Auto Mode

When an HTTP/HTTPS PAC URL is configured in Preferences → Advanced, GNOME uses that external PAC URL directly.

### Proxy Off

GNOME proxy is disabled and the managed proxy runtime is stopped.

## PAC rules

Use **Edit PAC User Rules…** from the tray menu. Examples:

```text
# proxy this domain
google.com

# force direct
@@internal.example.com
```

Use **Update PAC from GFWList** to refresh the remote rule list. The previous valid copy is preserved if an update fails validation.

## Development

```bash
python3 -m pip install -e '.[dev]'
python3 -m compileall -q ssxng
pytest -q --cov=ssxng --cov-branch
ruff check ssxng tests
```

Active development is on `dev/mvp`.

## MVP release checklist

Before tagging a release, verify:

1. PAC, Global, Manual and External PAC mode switching.
2. Browser access and terminal access through the HTTP bridge.
3. Server switching, invalid server handling, plugin presence and port conflicts.
4. GFWList success/failure behavior and user PAC rules.
5. Normal Quit, `Ctrl+C`, duplicate launch and recovery after an unclean previous exit.
6. Preferences persistence and start-at-login behavior.
7. Dialog layout under light/dark themes and Simplified Chinese/English locales.
8. `ssx-ng-tool health` reports all configured listeners correctly.
9. `.deb` install, reinstall/upgrade and package payload smoke checks.

## License

GPL-3.0-or-later.

This project is not an official Shadowsocks project.
