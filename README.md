# LibreWing

[![CI](https://github.com/fattoliu/librewing/actions/workflows/ci.yml/badge.svg)](https://github.com/fattoliu/librewing/actions/workflows/ci.yml)
[![License: GPL-3.0-or-later](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB.svg)](https://www.python.org/)

A lightweight Shadowsocks desktop controller designed for GNOME and Ubuntu,
with a tray-first workflow and native system-proxy integration.

LibreWing combines `ss-local`, SIP003 plugins, GFWList rules, server profiles,
and a local HTTP bridge behind a focused Linux desktop interface.

LibreWing is an independent community project. It does not provide proxy
servers, VPS hosting, subscriptions, accounts, or network access services.

> **Project status:** stable. Ubuntu 24.04 or newer with GNOME is officially
> supported on amd64 and arm64. See [ROADMAP.md](ROADMAP.md).

## Current feature set

- StatusNotifierItem/DBusMenu tray UI with original LibreWing status icons
- Smart Routing / All Traffic / Local Proxy Only / Custom PAC modes
- Distinct geometric status markers for each routing mode
- Multiple Shadowsocks server profiles and profile switching
- Server settings window with SIP003 plugin/plugin options
- `ss://` URL import, clipboard import, QR scan and QR sharing
- Server TCP latency test
- Managed `ss-local` lifecycle and orphan-process recovery
- Native local HTTP → SOCKS5 bridge for terminal/application proxy use
- Local PAC server with GFWList and custom user rules
- Foreground GFWList update with cached last-known-good data
- GNOME system proxy integration
- Focused Settings window: General / Advanced / HTTP / Network Interface
- Start-at-login integration
- Localized UI following the system locale (Simplified Chinese, Traditional Chinese, English fallback)
- Logs, diagnostics export, update/help links
- Native `.deb` package with automatic `shadowsocks-libev` dependency installation
- Bundled `obfs-local` runtime for simple-obfs server profiles
- Health-check CLI via `librewing-tool health`
- GitHub Actions unit, desktop-import and Debian-package smoke tests

## Architecture

```text
GNOME / Ubuntu tray
        │
        ├── Routing / active profile
        ├── Import / tools / diagnostics
        └── connection mode
              │
              ├── Disconnected     → runtime stopped; GNOME proxy disabled
              ├── Local Proxy Only → local services available; GNOME proxy disabled
              ├── Smart Routing    → GNOME auto proxy → local /proxy.pac
              ├── All Traffic      → GNOME auto proxy → local /global.pac
              └── Custom PAC       → GNOME auto proxy → configured external PAC URL
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

Supported release baseline: Ubuntu 24.04 or newer with GNOME, on amd64 or
arm64. Other Debian-based distributions may work but are not currently part of
the release test matrix.

Non-GNOME desktops can use Local Proxy Only with application-level HTTP/SOCKS/PAC
configuration, but automatic system-proxy integration is GNOME-only. Tray and
screen-capture support depend on the desktop's StatusNotifier and portal
implementations. See the [platform support matrix](docs/platform-support.md).

Package installation and runtime imports are also smoke-tested against Ubuntu
26.04's Python 3.14 desktop stack.

For a published version, download the package for your architecture from
[GitHub Releases](https://github.com/fattoliu/librewing/releases),
then install it with dependency resolution:

```bash
sudo apt install ./librewing_VERSION_ARCH.deb
```

For source builds:

```bash
git clone https://github.com/fattoliu/librewing.git
cd librewing
bash scripts/install-ubuntu.sh
```

Run the installed native package entrypoint:

```bash
librewing
```

Useful diagnostics:

```bash
librewing-tool health
```

### Upgrading from ShadowsocksX-NG Linux 1.0

Installing LibreWing replaces the former Debian package without deleting user
settings. On first launch, `~/.config/shadowsocksx-ng-linux` moves to
`~/.config/librewing`. Existing backups, autostart entries, and the legacy
`ssx-ng-linux` / `ssx-ng-tool` commands remain compatible.

The Debian package installs the desktop client into `/usr/bin` and its Python modules under `/usr/lib/librewing`.

Users do **not** need to install `shadowsocks-libev` or `simple-obfs` manually before using the application:

- `shadowsocks-libev` is declared as a Debian dependency, so `apt` installs `ss-local` automatically.
- `obfs-local` is shipped inside the application package at `/usr/lib/librewing/bin/obfs-local`.
- A server profile can simply use `obfs-local` as its plugin value; the application resolves the bundled executable before looking in the system `PATH`.

Example:

```text
Plugin: obfs-local
Plugin options: obfs=tls
```

The bundled simple-obfs runtime uses Ubuntu 24.04 as its compatibility baseline
and supports amd64/arm64. Other SIP003 plugins remain externally installable
and are detected automatically.

## Listener security

SOCKS5, HTTP proxy, and PAC services listen on loopback by default. The SOCKS5
and HTTP services do not authenticate clients, so a non-loopback listen address
is rejected unless its corresponding **Allow … From LAN** preference is also
enabled. Only enable LAN access on a trusted network with an appropriate host
firewall.

Configuration, runtime state, logs, backups, and exported server files can
contain credentials or sensitive connection details. They are written with
owner-only permissions. Do not attach them to public issues without redaction.

## Terminal proxy

The desktop client's local HTTP proxy defaults to `127.0.0.1:1087`. A shell can opt in with environment variables:

```bash
export http_proxy=http://127.0.0.1:1087
export https_proxy=http://127.0.0.1:1087
```

The tray menu also provides **Tools → Copy Terminal Proxy Setup**.

## Modes

### Smart Routing

The local PAC server uses GFWList plus user rules to decide whether a destination should use Shadowsocks or connect directly.

### All Traffic

The local global PAC endpoint sends all normal traffic through the local proxy bridge. Using a PAC endpoint also avoids inconsistent SOCKS-only handling across GNOME applications.

### Local Proxy Only

`ss-local` and enabled local proxy services remain available, but GNOME system proxy settings are disabled. Applications can opt in manually.

### Custom PAC

When an HTTP/HTTPS PAC URL is configured in Settings → Advanced, GNOME uses that external PAC URL directly.

### Disconnected

GNOME proxy is disabled and the managed proxy runtime is stopped.

## PAC rules

Use **Tools → Edit Routing Rules…** from the tray menu. Examples:

```text
# proxy this domain
google.com

# force direct
@@internal.example.com

# disable a rule without deleting it
! disabled: google.com
```

Use **Tools → Refresh Smart Routing Rules** to refresh the remote rule list. The previous valid copy is preserved if an update fails validation.

## Development

```bash
python3 -m pip install -e '.[dev]'
python3 -m compileall -q ssxng
pytest -q --cov=ssxng --cov-branch
ruff check ssxng tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for Ubuntu dependencies, quality gates,
and pull-request expectations. Architecture and release details live under
[`docs/`](docs/architecture.md).

### Debian package build

```bash
bash scripts/build-deb.sh
```

By default the build embeds `obfs-local`. It downloads the pinned Ubuntu 24.04
amd64/arm64 source package, verifies its architecture-specific SHA-256, and
extracts only the client runtime. Builds never silently reuse a binary from
`PATH`. Set `SIMPLE_OBFS_BINARY=/absolute/path/to/obfs-local` for an explicit
development override, or `BUNDLE_SIMPLE_OBFS=0` for a build that intentionally
omits it. Official releases must use the pinned artifacts.

The build timestamp defaults to the current Git commit, making repeated builds
of the same revision byte-for-byte reproducible. When building from a source
archive without Git metadata, set `SOURCE_DATE_EPOCH` to the archive's revision
timestamp explicitly.

Release assets include a deterministic SPDX 2.3 software bill of materials for
each architecture. The SBOM lists every installed file with its SHA-256 digest
and binds the document to the corresponding Debian package checksum.
Tagged public releases also receive GitHub/Sigstore SLSA build-provenance and
SBOM attestations, verifiable with `gh attestation verify`.

## MVP release checklist

Before tagging a release, verify:

1. Smart Routing, All Traffic, Local Proxy Only and Custom PAC switching.
2. Browser access and terminal access through the HTTP bridge.
3. Server switching, invalid server handling, bundled simple-obfs and port conflicts.
4. GFWList success/failure behavior and user PAC rules.
5. Normal Quit, `Ctrl+C`, duplicate launch and recovery after an unclean previous exit.
6. Settings persistence and start-at-login behavior.
7. Dialog layout, keyboard navigation, and accessible labels under light/dark themes and Simplified Chinese/Traditional Chinese/English locales.
8. `librewing-tool health` reports all configured listeners correctly.
9. Clean-machine `.deb` install: `ss-local` is installed automatically and bundled `obfs-local` is executable without any manual prerequisite setup.

## Support development

If LibreWing has made your day a little easier, you can buy me a coffee ☕.
A star, useful feedback, or a code contribution is equally appreciated.

如果 LibreWing 帮你省了一点时间，欢迎请我喝杯咖啡 ☕。Star、反馈和代码贡献也同样珍贵。

<table>
  <tr>
    <th>Alipay / 支付宝</th>
    <th>WeChat Pay / 微信支付</th>
  </tr>
  <tr>
    <td><img src="assets/sponsor/alipay.jpg" alt="Alipay sponsorship QR code" width="260"></td>
    <td><img src="assets/sponsor/wechat-pay.jpg" alt="WeChat Pay sponsorship QR code" width="260"></td>
  </tr>
</table>

<sub>Voluntary support only. No proxy servers, VPS hosting, subscriptions,
accounts, network access, paid features, or priority support are provided.<br>
仅为自愿赞助，不提供代理服务、服务器、VPS、订阅、账号、网络访问、付费功能或优先支持；收款由维护者依法处理。</sub>

## License

GPL-3.0-or-later. See [LICENSE](LICENSE) for the complete license and
[NOTICE](NOTICE) for acknowledgements and bundled third-party software.

This project is not an official Shadowsocks project.

## Acknowledgements

[ShadowsocksX-NG](https://github.com/shadowsocks/ShadowsocksX-NG) helped inspire
the original idea for a convenient desktop Shadowsocks controller. LibreWing
uses its own Linux implementation, product structure, wording, and visual assets.
