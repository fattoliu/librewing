#!/usr/bin/env bash
set -euo pipefail

if ! command -v apt >/dev/null 2>&1; then
  echo "This installer currently targets Ubuntu/Debian." >&2
  exit 1
fi

sudo apt update
sudo apt install -y \
  python3 python3-pip python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 \
  shadowsocks-libev privoxy libayatana-appindicator3-1 qrencode zbar-tools

python3 -m pip install --user --break-system-packages .

mkdir -p "$HOME/.config/autostart" "$HOME/.local/share/applications"
DESKTOP_CONTENT="[Desktop Entry]
Type=Application
Name=ShadowsocksX-NG Linux
Comment=Shadowsocks desktop proxy client
Exec=$HOME/.local/bin/ssx-ng-linux
Icon=network-vpn-symbolic
Terminal=false
X-GNOME-Autostart-enabled=true
Categories=Network;Utility;
StartupNotify=false"

printf '%s\n' "$DESKTOP_CONTENT" > "$HOME/.config/autostart/shadowsocksx-ng-linux.desktop"
printf '%s\n' "$DESKTOP_CONTENT" > "$HOME/.local/share/applications/shadowsocksx-ng-linux.desktop"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$HOME/.local/share/applications" || true

echo
echo "Installed successfully."
echo "Run: $HOME/.local/bin/ssx-ng-linux"
echo "simple-obfs: install obfs-local separately if your server requires it."

if systemctl is-active --quiet shadowsocks-libev-local@config.service 2>/dev/null; then
  echo
  echo "NOTICE: shadowsocks-libev-local@config.service is already running."
  echo "It may occupy port 1080 and conflict with the desktop client."
  echo "When you are ready to use the desktop client, stop it with:"
  echo "  sudo systemctl disable --now shadowsocks-libev-local@config.service"
fi
