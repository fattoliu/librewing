#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VERSION:-0.2.0}"
ARCH="${ARCH:-amd64}"
PKG="$ROOT/dist/shadowsocksx-ng-linux_${VERSION}_${ARCH}"
OUT="$ROOT/dist/shadowsocksx-ng-linux_${VERSION}_${ARCH}.deb"
ICON_ASSETS="$ROOT/assets/upstream"
ICON_OUT="$PKG/usr/share/icons/hicolor/44x44/status"

rm -rf "$PKG"
mkdir -p \
  "$PKG/DEBIAN" \
  "$PKG/usr/bin" \
  "$PKG/usr/lib/shadowsocksx-ng-linux" \
  "$PKG/usr/share/applications" \
  "$ICON_OUT"

cp -R "$ROOT/ssxng" "$PKG/usr/lib/shadowsocksx-ng-linux/"

# These are the original ShadowsocksX-NG @2x status-bar PNG assets, vendored
# in the source tree as base64 text so local package builds never need network
# access. The active P/G/M icons keep the exact upstream silhouette and alpha
# but are recolored to bright white for Ubuntu's dark top panel; the disabled
# icon stays in the original muted gray so On/Off is visually obvious.
declare -A ICONS=(
  [shadowsocksx-ng-linux]="menu_icon@2x.png"
  [shadowsocksx-ng-linux-disabled]="menu_icon_disabled@2x.png"
  [shadowsocksx-ng-linux-pac]="menu_p_icon@2x.png"
  [shadowsocksx-ng-linux-global]="menu_g_icon@2x.png"
  [shadowsocksx-ng-linux-manual]="menu_m_icon@2x.png"
)

for icon_name in "${!ICONS[@]}"; do
  upstream_name="${ICONS[$icon_name]}"
  encoded="$ICON_ASSETS/$upstream_name.b64"
  decoded="$PKG/$upstream_name"
  target="$ICON_OUT/$icon_name.png"

  if [ ! -s "$encoded" ]; then
    echo "Missing vendored tray icon asset: $encoded" >&2
    exit 1
  fi

  base64 --decode "$encoded" > "$decoded"

  case "$icon_name" in
    shadowsocksx-ng-linux-pac|shadowsocksx-ng-linux-global|shadowsocksx-ng-linux-manual|shadowsocksx-ng-linux)
      python3 "$ROOT/scripts/recolor-png.py" "$decoded" "$target" 255 255 255
      ;;
    *)
      cp "$decoded" "$target"
      ;;
  esac
  rm -f "$decoded"
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
