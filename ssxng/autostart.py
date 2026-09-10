from __future__ import annotations

import os
from pathlib import Path

APP_ID = "librewing"
AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / f"{APP_ID}.desktop"
LEGACY_AUTOSTART_FILE = AUTOSTART_DIR / "shadowsocksx-ng-linux.desktop"


def desktop_entry(exec_path: str | None = None) -> str:
    executable = (
        exec_path
        or os.environ.get("LIBREWING_EXECUTABLE")
        or os.environ.get("SSXNG_EXECUTABLE")
        or "librewing"
    )
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            "Name=LibreWing",
            "Comment=Shadowsocks desktop proxy client",
            f"Exec={executable}",
            "Icon=librewing-app",
            "Terminal=false",
            "X-GNOME-Autostart-enabled=true",
            "Categories=Network;Utility;",
            "StartupNotify=false",
            "",
        ]
    )


def is_enabled(path: Path | None = None) -> bool:
    target = path or (AUTOSTART_FILE if AUTOSTART_FILE.exists() else LEGACY_AUTOSTART_FILE)
    if not target.exists():
        return False
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return False
    return "X-GNOME-Autostart-enabled=true" in text


def set_enabled(enabled: bool, exec_path: str | None = None, path: Path | None = None) -> None:
    target = path or AUTOSTART_FILE
    if enabled:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(desktop_entry(exec_path), encoding="utf-8")
        if path is None:
            LEGACY_AUTOSTART_FILE.unlink(missing_ok=True)
    else:
        target.unlink(missing_ok=True)
        if path is None:
            LEGACY_AUTOSTART_FILE.unlink(missing_ok=True)
