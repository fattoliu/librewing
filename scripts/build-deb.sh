#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VERSION:-0.2.0}"
ARCH="${ARCH:-amd64}"
PKG="$ROOT/dist/shadowsocksx-ng-linux_${VERSION}_${ARCH}"
OUT="$ROOT/dist/shadowsocksx-ng-linux_${VERSION}_${ARCH}.deb"

rm -rf "$PKG"
mkdir -p \
  "$PKG/DEBIAN" \
  "$PKG/usr/bin" \
  "$PKG/usr/lib/shadowsocksx-ng-linux" \
  "$PKG/usr/share/applications"

cp -R "$ROOT/ssxng" "$PKG/usr/lib/shadowsocksx-ng-linux/"

cat > "$PKG/usr/bin/ssx-ng-linux" <<'EOF'
#!/usr/bin/env bash
export PYTHONPATH="/usr/lib/shadowsocksx-ng-linux${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m ssxng.app "$@"
EOF
chmod 755 "$PKG/usr/bin/ssx-ng-linux"

cat > "$PKG/usr/share/applications/shadowsocksx-ng-linux.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=ShadowsocksX-NG Linux
Comment=Shadowsocks desktop proxy client
Exec=ssx-ng-linux
Icon=network-vpn-symbolic
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
Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1, shadowsocks-libev, privoxy, libayatana-appindicator3-1, qrencode, zbar-tools
Description: Shadowsocks desktop client for Linux/Ubuntu
 Tray-first Shadowsocks client with PAC, GFWList, SIP003 plugins and GNOME proxy integration.
EOF

dpkg-deb --build --root-owner-group "$PKG" "$OUT"
echo "$OUT"
