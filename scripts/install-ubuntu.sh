#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v apt >/dev/null 2>&1; then
  echo "This installer currently targets Ubuntu/Debian." >&2
  exit 1
fi

if ! command -v dpkg-deb >/dev/null 2>&1; then
  echo "dpkg-deb is required on Ubuntu/Debian." >&2
  exit 1
fi

cd "$ROOT"

# A running tray process keeps already-imported Python modules in memory. During
# rapid development that can make a freshly reinstalled package appear to have
# "not changed" at all: the old tray keeps dispatching its old callbacks even
# though /usr/lib contains the new files. Stop only this application's launcher
# before replacing the package so the next start always loads the new code.
if pgrep -f 'python3 .*ssxng\.launcher|python3 -m ssxng\.launcher' >/dev/null 2>&1; then
  echo "Stopping running ShadowsocksX-NG Linux instance..."
  pkill -TERM -f 'python3 .*ssxng\.launcher|python3 -m ssxng\.launcher' || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ! pgrep -f 'python3 .*ssxng\.launcher|python3 -m ssxng\.launcher' >/dev/null 2>&1; then
      break
    fi
    sleep 0.1
  done
fi

# Build a native .deb from the checked-out source. The package declares all
# runtime dependencies, so apt installs them without touching pip/pipx or the
# externally-managed system Python environment (PEP 668).
bash scripts/build-deb.sh >/dev/null
DEB="$(ls -t dist/shadowsocksx-ng-linux_*.deb | head -n1)"

# During development the package version may stay the same while its contents
# change. --reinstall ensures the freshly rebuilt local .deb replaces the
# currently installed files instead of apt saying "already newest".
sudo apt install -y --reinstall "./$DEB"

# Remove only stale launchers created by older pip --user based installers.
# Never remove arbitrary user Python packages or run autoremove here.
for app in ssx-ng-linux ssx-ng-tool; do
  stale="$HOME/.local/bin/$app"
  if [ -e "$stale" ] || [ -L "$stale" ]; then
    if grep -q 'site-packages\|python.*ssxng' "$stale" 2>/dev/null; then
      rm -f "$stale"
    fi
  fi
done

# Remove the old per-user desktop entry if it points at ~/.local/bin. The .deb
# installs the canonical desktop entry under /usr/share/applications.
USER_DESKTOP="$HOME/.local/share/applications/shadowsocksx-ng-linux.desktop"
if [ -f "$USER_DESKTOP" ] && grep -q "$HOME/.local/bin/ssx-ng-linux" "$USER_DESKTOP"; then
  rm -f "$USER_DESKTOP"
fi

command -v update-desktop-database >/dev/null 2>&1 && sudo update-desktop-database /usr/share/applications || true

echo
echo "Installed successfully from native Debian package."
echo "Run: /usr/bin/ssx-ng-linux"
echo "Package: $DEB"
echo "No pip, pipx, venv, or --break-system-packages is used."
echo "simple-obfs: install obfs-local separately if your server requires it."

if systemctl is-active --quiet shadowsocks-libev-local@config.service 2>/dev/null; then
  echo
  echo "NOTICE: shadowsocks-libev-local@config.service is already running."
  echo "It may occupy port 1080 and conflict with the desktop client."
  echo "When you are ready to switch to this desktop client, stop it with:"
  echo "  sudo systemctl disable --now shadowsocks-libev-local@config.service"
fi
