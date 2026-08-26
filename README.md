# ShadowsocksX-NG Linux

A Linux/Ubuntu desktop client inspired by [ShadowsocksX-NG](https://github.com/shadowsocks/ShadowsocksX-NG).

The goal is to reproduce the day-to-day ShadowsocksX-NG experience on GNOME/Ubuntu while using native Linux building blocks instead of trying to compile the original Cocoa UI.

## Current implementation

The first runnable port already includes:

- GNOME system tray via Ayatana AppIndicator
- Shadowsocks server profiles
- `ss-local` process management
- SIP003 plugin fields (`plugin` / `plugin_opts`), including `simple-obfs`
- PAC mode
- Global SOCKS mode
- Manual mode
- Proxy off mode
- Embedded PAC HTTP server
- Custom PAC-rule storage
- GNOME `gsettings` proxy integration
- Automatic startup desktop entry
- Automatic discovery of `obfs-local`

The core architecture intentionally follows the modern ShadowsocksX-NG design: the GUI controls an external `ss-local` process rather than embedding the Shadowsocks implementation.

## Ubuntu dependencies

```bash
sudo apt install -y \
  python3 python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 \
  shadowsocks-libev libayatana-appindicator3-1
```

For `simple-obfs`, install `obfs-local` separately. The application can use `/usr/local/bin/obfs-local` or any `obfs-local` available in `PATH`.

## Run from source

```bash
git clone https://github.com/fattoliu/shadowsocksx-ng-linux.git
cd shadowsocksx-ng-linux
git checkout dev/mvp
python3 -m pip install --user --break-system-packages .
~/.local/bin/ssx-ng-linux
```

Or use the Ubuntu installer:

```bash
bash scripts/install-ubuntu.sh
```

## Server example

In **Servers → Add Server…** enter values equivalent to:

```json
{
  "server": "your-server",
  "server_port": 8388,
  "password": "your-password",
  "method": "aes-256-gcm",
  "plugin": "obfs-local",
  "plugin_opts": "obfs=tls",
  "local_port": 1080
}
```

## Migration roadmap

The original ShadowsocksX-NG feature set also includes capabilities that are not finished yet in this Linux port:

- GFWList download/update and conversion
- Full custom PAC-rule editor UI
- `ss://` URL import/export
- Clipboard import
- QR-code generation and scanning
- HTTP proxy / Privoxy integration
- Embedded or managed plugin installation (`simple-obfs`, `v2ray-plugin`, `kcptun`)
- Server latency test and richer profile management
- Preferences window
- Debian package / AppImage packaging
- Automated tests and GitHub Actions builds

## Development

Active development is currently on `dev/mvp`.

## License

GPL-3.0-or-later. This project is a Linux reimplementation inspired by ShadowsocksX-NG and is not an official Shadowsocks project.
