#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${VERSION:-0.3.0~rc.1}"
ARCH="${ARCH:-amd64}"
UBUNTU_VERSION="${UBUNTU_VERSION:-24.04}"
UBUNTU_SERIES="${UBUNTU_SERIES:-noble}"
BUNDLE_SIMPLE_OBFS="${BUNDLE_SIMPLE_OBFS:-1}"
if [ -z "${SOURCE_DATE_EPOCH:-}" ]; then
  if command -v git >/dev/null 2>&1 && SOURCE_DATE_EPOCH="$(git -C "$ROOT" log -1 --format=%ct 2>/dev/null)"; then
    :
  else
    echo "SOURCE_DATE_EPOCH is required when building outside a Git checkout." >&2
    exit 1
  fi
fi

if [[ ! "$VERSION" =~ ^[0-9][0-9A-Za-z.+:~_-]*$ ]]; then
  echo "Invalid Debian package version: $VERSION" >&2
  exit 1
fi
case "$ARCH" in
  amd64|arm64) ;;
  *)
    echo "Unsupported package architecture: $ARCH" >&2
    exit 1
    ;;
esac
if [[ ! "$SOURCE_DATE_EPOCH" =~ ^[0-9]+$ ]]; then
  echo "SOURCE_DATE_EPOCH must be an integer Unix timestamp." >&2
  exit 1
fi
export SOURCE_DATE_EPOCH

PKG="$ROOT/dist/shadowsocksx-ng-linux_${VERSION}_${ARCH}"
OUT="$ROOT/dist/shadowsocksx-ng-linux_${VERSION}_${ARCH}.deb"
ICON_ASSETS="$ROOT/assets/upstream"
ICON_OUT="$PKG/usr/share/icons/hicolor/36x36/status"
APP_LIB="$PKG/usr/lib/shadowsocksx-ng-linux"
APP_BIN="$APP_LIB/bin"

cleanup() {
  rm -rf "$PKG"
}
trap cleanup EXIT

rm -rf "$PKG"
mkdir -p \
  "$PKG/DEBIAN" \
  "$PKG/usr/bin" \
  "$APP_LIB" \
  "$APP_BIN" \
  "$PKG/usr/share/applications" \
  "$PKG/usr/share/man/man1" \
  "$PKG/usr/share/metainfo" \
  "$PKG/usr/share/doc/shadowsocksx-ng-linux" \
  "$ICON_OUT"

cp -R "$ROOT/ssxng" "$APP_LIB/"
find "$APP_LIB/ssxng" -type d -name __pycache__ -prune -exec rm -rf -- {} +
find "$APP_LIB/ssxng" -type f -name '*.pyc' -delete
cp "$ROOT/README.md" "$ROOT/CHANGELOG.md" "$ROOT/NOTICE" "$ROOT/LICENSE" \
  "$PKG/usr/share/doc/shadowsocksx-ng-linux/"
cp "$ROOT/packaging/copyright" "$PKG/usr/share/doc/shadowsocksx-ng-linux/copyright"
cp "$ROOT/packaging/io.github.fattoliu.shadowsocksxng.metainfo.xml" "$PKG/usr/share/metainfo/"
{
  printf 'shadowsocksx-ng-linux (%s) noble; urgency=medium\n\n' "$VERSION"
  printf '  * See /usr/share/doc/shadowsocksx-ng-linux/CHANGELOG.md for release details.\n\n'
  printf ' -- fattoliu <724684054@qq.com>  %s\n' "$(date -u -d "@$SOURCE_DATE_EPOCH" -R)"
} | gzip -9n > "$PKG/usr/share/doc/shadowsocksx-ng-linux/changelog.gz"
gzip -9n -c "$ROOT/packaging/ssx-ng-linux.1" > "$PKG/usr/share/man/man1/ssx-ng-linux.1.gz"
gzip -9n -c "$ROOT/packaging/ssx-ng-tool.1" > "$PKG/usr/share/man/man1/ssx-ng-tool.1.gz"

bundle_simple_obfs() {
  [ "$BUNDLE_SIMPLE_OBFS" = "1" ] || return 0

  local target="$APP_BIN/obfs-local"
  local supplied_obfs="${SIMPLE_OBFS_BINARY:-}"

  if [ -n "$supplied_obfs" ]; then
    if [ ! -x "$supplied_obfs" ]; then
      echo "SIMPLE_OBFS_BINARY is not an executable file: $supplied_obfs" >&2
      exit 1
    fi
    echo "Bundling explicitly supplied simple-obfs binary: $supplied_obfs" >&2
    cp "$supplied_obfs" "$target"
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
  local release="ubuntu.${UBUNTU_VERSION}~${UBUNTU_SERIES}"
  local filename="shadowsocks-simple-obfs_${version}~${release}_${ARCH}.deb"
  local base="https://dl.lamp.sh/shadowsocks/ubuntu/pool/main/s/shadowsocks-simple-obfs"
  local url="${SIMPLE_OBFS_DEB_URL:-$base/$filename}"
  local expected_sha256="${SIMPLE_OBFS_DEB_SHA256:-}"
  local tmp

  if [ -z "$expected_sha256" ]; then
    if [ -n "${SIMPLE_OBFS_DEB_URL:-}" ]; then
      echo "SIMPLE_OBFS_DEB_SHA256 is required with a custom SIMPLE_OBFS_DEB_URL." >&2
      exit 1
    fi
    case "$ARCH" in
      amd64) expected_sha256="8a8c7decd284fab9a3f9d8ececec69e72c78987f5994b980bba5a15b3f7457f3" ;;
      arm64) expected_sha256="568702496c713ba0cd971c6575bf454354fea34f0f3b7f5682effa4af32ea9c0" ;;
    esac
  fi
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' RETURN

  echo "Bundling simple-obfs runtime for $ARCH from $url" >&2
  env -u http_proxy -u https_proxy -u all_proxy \
      -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
    curl --noproxy '*' --fail --location --silent --show-error --retry 2 --connect-timeout 15 \
      --output "$tmp/simple-obfs.deb" "$url"
  echo "$expected_sha256  $tmp/simple-obfs.deb" | sha256sum --check --status || {
    echo "Downloaded simple-obfs package failed SHA-256 verification." >&2
    exit 1
  }
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
  [shadowsocksx-ng-linux-disabled]="menu_icon@2x.png"
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
    shadowsocksx-ng-linux-disabled)
      # Keep the off state distinct without disappearing into GNOME's dark panel.
      python3 "$ROOT/scripts/recolor-png.py" "$decoded" "$target" 160 160 160
      ;;
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

cat > "$PKG/usr/share/applications/io.github.fattoliu.shadowsocksxng.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=ShadowsocksX-NG Linux
Comment=Shadowsocks desktop proxy client
Exec=ssx-ng-linux
Icon=network-vpn-symbolic
Terminal=false
Categories=Network;
StartupNotify=false
EOF
chmod 644 "$PKG/usr/share/applications/io.github.fattoliu.shadowsocksxng.desktop"

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
Maintainer: fattoliu <724684054@qq.com>
Homepage: https://github.com/fattoliu/shadowsocksx-ng-linux
Depends: libc6, python3, python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, gir1.2-gdkpixbuf-2.0, gir1.2-dbusmenu-glib-0.4, libdbusmenu-glib4, libglib2.0-bin, gsettings-desktop-schemas, shadowsocks-libev, libcap2-bin, libcork16, libev4, qrencode, zbar-tools, curl
Recommends: shadowsocks-v2ray-plugin
Suggests: gnome-shell-extension-appindicator
Description: Shadowsocks desktop client for Linux/Ubuntu
 Tray-first Shadowsocks client with native SOCKS global mode, PAC, GFWList,
 bundled simple-obfs client support, SIP003 plugins and GNOME proxy integration.
 The tray uses StatusNotifierItem/DBusMenu, and all windows use GTK4/libadwaita.
EOF

find "$PKG" -print0 | xargs -0 touch --no-dereference --date="@$SOURCE_DATE_EPOCH"
dpkg-deb --build --root-owner-group "$PKG" "$OUT"
echo "$OUT"
