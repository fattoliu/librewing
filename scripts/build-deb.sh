#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VERSION:-0.2.0}"
ARCH="${ARCH:-amd64}"
UBUNTU_SERIES="${UBUNTU_SERIES:-resolute}"
BUNDLE_SIMPLE_OBFS="${BUNDLE_SIMPLE_OBFS:-1}"
PKG="$ROOT/dist/shadowsocksx-ng-linux_${VERSION}_${ARCH}"
OUT="$ROOT/dist/shadowsocksx-ng-linux_${VERSION}_${ARCH}.deb"
ICON_ASSETS="$ROOT/assets/upstream"
ICON_OUT="$PKG/usr/share/icons/hicolor/44x44/status"
APP_ICON_OUT="$PKG/usr/share/icons/hicolor/scalable/apps"
APP_LIB="$PKG/usr/lib/shadowsocksx-ng-linux"
APP_BIN="$APP_LIB/bin"

rm -rf "$PKG"
mkdir -p \
  "$PKG/DEBIAN" \
  "$PKG/usr/bin" \
  "$APP_LIB" \
  "$APP_BIN" \
  "$PKG/usr/share/applications" \
  "$PKG/usr/share/doc/shadowsocksx-ng-linux" \
  "$ICON_OUT" \
  "$APP_ICON_OUT"

cp -R "$ROOT/ssxng" "$APP_LIB/"

bundle_simple_obfs() {
  [ "$BUNDLE_SIMPLE_OBFS" = "1" ] || return 0

  local target="$APP_BIN/obfs-local"
  local system_obfs=""
  system_obfs="$(command -v obfs-local 2>/dev/null || true)"

  # Development builds can reuse an already-installed executable. Official or
  # clean builders fall through to the architecture-specific package below.
  if [ -n "$system_obfs" ] && [ -x "$system_obfs" ]; then
    echo "Bundling simple-obfs from $system_obfs" >&2
    cp "$system_obfs" "$target"
    chmod 755 "$target"
    return 0
  fi

  case "$ARCH" in
    amd64|arm64) ;;
    *)
      echo "No bundled simple-obfs binary source is configured for architecture: $ARCH" >&2
      echo "Set BUNDLE_SIMPLE_OBFS=0 or provide obfs-local in PATH." >&2
      exit 1
      ;;
  esac

  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to assemble the bundled simple-obfs runtime." >&2
    exit 1
  fi

  local version="0.0.5-1"
  local release="ubuntu.26.04~${UBUNTU_SERIES}"
  local filename="shadowsocks-simple-obfs_${version}~${release}_${ARCH}.deb"
  local base="https://dl.lamp.sh/shadowsocks/ubuntu/pool/main/s/shadowsocks-simple-obfs"
  local url="${SIMPLE_OBFS_DEB_URL:-$base/$filename}"
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  echo "Bundling simple-obfs runtime for $ARCH from $url" >&2
  env -u http_proxy -u https_proxy -u all_proxy \
      -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
    curl --noproxy '*' --fail --location --silent --show-error --retry 2 --connect-timeout 15 \
      --output "$tmp/simple-obfs.deb" "$url"
  dpkg-deb -x "$tmp/simple-obfs.deb" "$tmp/root"

  if [ ! -x "$tmp/root/usr/bin/obfs-local" ]; then
    echo "Downloaded simple-obfs package does not contain /usr/bin/obfs-local" >&2
    exit 1
  fi
  cp "$tmp/root/usr/bin/obfs-local" "$target"
  chmod 755 "$target"

  local copyright
  copyright="$(find "$tmp/root/usr/share/doc" -maxdepth 2 -name copyright -print -quit 2>/dev/null || true)"
  if [ -n "$copyright" ]; then
    cp "$copyright" "$PKG/usr/share/doc/shadowsocksx-ng-linux/simple-obfs-copyright"
  fi

  rm -rf "$tmp"
  trap - RETURN
}

bundle_simple_obfs

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

# Desktop/application icon. Keep this separate from the monochrome tray icon:
# GNOME's application grid needs a full-size app icon, otherwise it can fall
# back to a generic gear. This deliberately restores the compact VPN badge
# used by the early Linux builds.
cat > "$APP_ICON_OUT/shadowsocksx-ng-linux.svg" <<'EOF'
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#5B8CFF"/>
      <stop offset="1" stop-color="#6D5DFB"/>
    </linearGradient>
  </defs>
  <rect x="16" y="16" width="224" height="224" rx="52" fill="url(#bg)"/>
  <path d="M128 50c28 19 51 25 68 28v43c0 43-25 72-68 91-43-19-68-48-68-91V78c17-3 40-9 68-28z" fill="#fff" fill-opacity=".16" stroke="#fff" stroke-width="8" stroke-linejoin="round"/>
  <rect x="69" y="103" width="118" height="55" rx="18" fill="#fff"/>
  <text x="128" y="140" text-anchor="middle" font-family="DejaVu Sans, sans-serif" font-size="34" font-weight="700" letter-spacing="2" fill="#5D67E8">VPN</text>
</svg>
EOF
chmod 644 "$APP_ICON_OUT/shadowsocksx-ng-linux.svg"

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
chmod 644 "$PKG/usr/share/applications/shadowsocksx-ng-linux.desktop"

# Refresh GNOME's application and icon caches automatically after installing
# or upgrading the package. These commands are optional on minimal systems.
cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 755 "$PKG/DEBIAN/postinst"

cat > "$PKG/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
case "$1" in
  remove|purge)
    if command -v update-desktop-database >/dev/null 2>&1; then
      update-desktop-database /usr/share/applications || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
      gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
    ;;
esac
exit 0
EOF
chmod 755 "$PKG/DEBIAN/postrm"

cat > "$PKG/DEBIAN/control" <<EOF
Package: shadowsocksx-ng-linux
Version: $VERSION
Section: net
Priority: optional
Architecture: $ARCH
Maintainer: fattoliu
Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-gtk-4.0, gir1.2-adw-1, gir1.2-ayatanaappindicator3-0.1, shadowsocks-libev, libayatana-appindicator3-1, qrencode, zbar-tools, curl
Recommends: shadowsocks-v2ray-plugin
Description: Shadowsocks desktop client for Linux/Ubuntu
 Tray-first Shadowsocks client with native SOCKS global mode, PAC, GFWList, bundled simple-obfs client support, SIP003 plugins and GNOME proxy integration. Modern settings windows use GTK4/libadwaita in isolated helper processes while the tray remains compatible with AppIndicator/GTK3.
EOF

dpkg-deb --build --root-owner-group "$PKG" "$OUT"
echo "$OUT"
