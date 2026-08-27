#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VERSION:-0.2.0}"
ARCH="${ARCH:-amd64}"
PKG="$ROOT/dist/shadowsocksx-ng-linux_${VERSION}_${ARCH}"
OUT="$ROOT/dist/shadowsocksx-ng-linux_${VERSION}_${ARCH}.deb"

# Pin the upstream revision so the tray artwork is the exact ShadowsocksX-NG
# asset set, not a hand-drawn approximation that may drift over time.
SSXNG_ASSET_REV="2357b07fdc2b8c82b7d40e73a9e4b20ca400c8f7"
SSXNG_ASSET_BASE="https://raw.githubusercontent.com/shadowsocks/ShadowsocksX-NG/${SSXNG_ASSET_REV}/ShadowsocksX-NG/images"
ICON_CACHE="$ROOT/dist/upstream-icons"

rm -rf "$PKG"
mkdir -p \
  "$PKG/DEBIAN" \
  "$PKG/usr/bin" \
  "$PKG/usr/lib/shadowsocksx-ng-linux" \
  "$PKG/usr/share/applications" \
  "$PKG/usr/share/icons/hicolor/44x44/status" \
  "$ICON_CACHE"

cp -R "$ROOT/ssxng" "$PKG/usr/lib/shadowsocksx-ng-linux/"

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to fetch the pinned ShadowsocksX-NG tray icon assets." >&2
  exit 1
fi

# Use the official @2x status-bar assets directly. GNOME/AppIndicator scales
# the source for the panel DPI, while the original P/G/M glyph stays legible.
declare -A ICONS=(
  [shadowsocksx-ng-linux]="menu_icon@2x.png"
  [shadowsocksx-ng-linux-disabled]="menu_icon_disabled@2x.png"
  [shadowsocksx-ng-linux-pac]="menu_p_icon@2x.png"
  [shadowsocksx-ng-linux-global]="menu_g_icon@2x.png"
  [shadowsocksx-ng-linux-manual]="menu_m_icon@2x.png"
)

for icon_name in "${!ICONS[@]}"; do
  upstream_name="${ICONS[$icon_name]}"
  cached="$ICON_CACHE/$upstream_name"
  if [ ! -s "$cached" ]; then
    echo "Fetching upstream tray icon: $upstream_name" >&2
    curl -fL --retry 3 --connect-timeout 10 \
      "$SSXNG_ASSET_BASE/$upstream_name" \
      -o "$cached"
  fi
  cp "$cached" "$PKG/usr/share/icons/hicolor/44x44/status/$icon_name.png"
done

cat > "$PKG/usr/bin/ssx-ng-linux" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH="/usr/lib/shadowsocksx-ng-linux${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m ssxng.launcher "$@"
EOF
chmod 755 "$PKG/usr/bin/ssx-ng-linux"

cat > "$PKG/usr/bin/ssx-ng-tool" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH="/usr/lib/shadowsocksx-ng-linux${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m ssxng.cli "$@"
EOF
chmod 755 "$PKG/usr/bin/ssx-ng-tool"

cat > "$PKG/usr/share/applications/shadowsocksx-ng-linux.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=ShadowsocksX-NG Linux
Comment=Shadowsocks desktop proxy client
Exec=ssx-ng-linux
Icon=shadowsocksx-ng-linux
Terminal=false
Categories=Network;Utility;
StartupNotify=false
EOF

cat > "$PKG/DEBIAN/control" <<EOF
Package: shadowsocksx-ng-linux
Version: $VERSION
Section: net
Priority: optional
Architecture: $ARCH
Maintainer: fattoliu
Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1, shadowsocks-libev, libayatana-appindicator3-1, qrencode, zbar-tools, curl
Description: Shadowsocks desktop client for Linux/Ubuntu
 Tray-first Shadowsocks client with native SOCKS global mode, PAC, GFWList, SIP003 plugins and GNOME proxy integration.
EOF

dpkg-deb --build --root-owner-group "$PKG" "$OUT"
echo "$OUT"
