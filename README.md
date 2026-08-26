# ShadowsocksX-NG Linux

A practical Linux/Ubuntu Shadowsocks desktop client inspired by [ShadowsocksX-NG](https://github.com/shadowsocks/ShadowsocksX-NG).

The project keeps the useful architecture and workflows of ShadowsocksX-NG—external `ss-local`, SIP003 plugins, PAC rules, GFWList and a tray-first UI—while replacing macOS-only integration with Linux/GNOME equivalents.

## Current features

- Ayatana AppIndicator system tray
- Multiple Shadowsocks server profiles
- Add / edit / delete / switch profiles
- `ss://` URL import and export
- External `ss-local` process management
- SIP003 plugin/plugin options support
- `simple-obfs` support via `obfs-local`
- Managed Privoxy HTTP proxy layered on local SOCKS5
- **PAC Mode**
- **Global Mode**
- **Manual Mode**
- **Proxy Off**
- GNOME system proxy integration
- GFWList download/update with last-known-good cache
- User PAC rules
  - `domain.com` → proxy
  - `@@domain.com` → direct
  - `# comment`
- Background GFWList update
- PAC diagnostics and rule counts
- Desktop application entry and auto-start entry
- Unit tests and GitHub Actions CI

## Architecture

```text
GNOME tray UI
    │
    ├── server profiles / ss:// sharing
    ├── GFWList + user PAC rules
    └── mode switch
          │
          ├── Off      → GNOME proxy disabled
          ├── Manual   → local SOCKS5 only
          ├── Global   → GNOME HTTP/HTTPS → Privoxy
          └── PAC      → GNOME PAC → Privoxy
                                        │
                                        ▼
                                   ss-local
                                        │
                               SIP003 plugin
                             (e.g. simple-obfs)
                                        │
                                        ▼
                              Shadowsocks server
```

Privoxy is intentionally used for system proxy modes because Linux desktop applications are much more consistent about honoring HTTP/HTTPS proxy settings than a GNOME SOCKS-only configuration.

## Ubuntu install

```bash
git clone https://github.com/fattoliu/shadowsocksx-ng-linux.git
cd shadowsocksx-ng-linux
git checkout dev/mvp
bash scripts/install-ubuntu.sh
```

Then run:

```bash
~/.local/bin/ssx-ng-linux
```

The installer currently installs:

- Python 3 / PyGObject
- GTK 3
- Ayatana AppIndicator
- `shadowsocks-libev`
- Privoxy

If your server uses `simple-obfs`, install `obfs-local` separately and set:

```text
Plugin: obfs-local
Plugin options: obfs=tls
```

## Modes

### PAC Mode

GFWList and user rules decide which destinations use the local proxy. User DIRECT rules take precedence.

### Global Mode

GNOME HTTP and HTTPS system proxy settings point to the managed local Privoxy instance, which forwards through Shadowsocks.

### Manual Mode

The application keeps `ss-local` running but disables GNOME system proxy configuration. Applications can manually use `127.0.0.1:1080` (or the selected profile's local port).

### Proxy Off

GNOME system proxy is disabled.

## PAC rules

Open **PAC Rules → Edit User Rules…** from the tray menu.

```text
# proxy this domain
google.com

# force direct
@@internal.example.com
```

Use **PAC Rules → Update GFWList** to refresh the remote list. The previous working copy is preserved if downloading or validation fails.

## Development

```bash
python3 -m pip install -e '.[dev]'
pytest
```

Active development is on `dev/mvp` and tracked in draft PR #1.

## Near-term roadmap

- More complete Adblock/GFWList rule semantics compatible with ShadowsocksX-NG's `abp.js`
- Clipboard auto-detection for `ss://` links
- QR-code import/export
- Server latency testing
- Plugin discovery/management
- Preferences window
- Better logs and connectivity diagnostics
- `.deb` / AppImage release packaging
- Localization

## License

GPL-3.0-or-later.

This project is not an official Shadowsocks project.
