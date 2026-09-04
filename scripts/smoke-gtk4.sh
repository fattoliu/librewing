#!/usr/bin/env bash
set -euo pipefail

SMOKE_TMP="$(mktemp -d)"
trap 'rm -rf "$SMOKE_TMP"' EXIT

check_window() {
  local name="$1"
  shift
  set +e
  xvfb-run -a dbus-run-session -- timeout 2 "$@" \
    >"$SMOKE_TMP/$name.out" 2>"$SMOKE_TMP/$name.err"
  local status=$?
  set -e
  if [ "$status" -ne 124 ]; then
    cat "$SMOKE_TMP/$name.out" "$SMOKE_TMP/$name.err" >&2
    echo "$name failed to remain open (status $status)" >&2
    return 1
  fi
}

check_window alert python3 -m ssxng.modern_ui4 alert smoke
check_window input python3 -m ssxng.modern_ui4 input Import Placeholder
check_window preferences python3 -m ssxng.modern_ui4 preferences
check_window rules python3 -m ssxng.modern_ui4 rules
check_window logs python3 -m ssxng.modern_ui4 logs
check_window viewer python3 -m ssxng.modern_ui4 viewer Title Text
check_window share python3 -m ssxng.modern_ui4 share Demo ss://test
check_window about python3 -m ssxng.feedback_ui4 about
check_window servers python3 -m ssxng.server_manager4

echo "GTK4 windows started successfully"
