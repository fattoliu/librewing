#!/usr/bin/env bash
set -euo pipefail

if ! command -v apt >/dev/null 2>&1; then
  echo "This installer currently targets Ubuntu/Debian." >&2
  exit 1
fi

sudo apt update
sudo apt install -y \
  python3 python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 \
  shadowsocks-libev libayatana-appindicator3-1

python3 -m pip install --user --break-system-packages .

mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/shadowsocksx-ng-linux.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ShadowsocksX-NG Linux
Comment=Shadowsocks desktop proxy client
Exec=$HOME/.local/bin/ssx-ng-linux
Icon=network-vpn-symbolic
Terminal=false
X-GNOME-Autostart-enabled=true
Categories=Network;
EOF

echo
echo "Installed. Run: $HOME/.local/bin/ssx-ng-linux"
echo "For simple-obfs, ensure obfs-local is installed and select it in the server profile."
