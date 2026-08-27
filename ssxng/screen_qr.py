from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class ScreenQrError(RuntimeError):
    pass


def _capture_screen(image: Path) -> None:
    """Capture the GNOME desktop without requiring a new package.

    Prefer gnome-screenshot when it already exists. Otherwise use GNOME
    Shell's D-Bus screenshot API through gdbus, which is part of the standard
    Ubuntu desktop stack.
    """
    screenshot = shutil.which("gnome-screenshot")
    if screenshot:
        result = subprocess.run(
            [screenshot, "-f", str(image)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0 and image.exists():
            return

    gdbus = shutil.which("gdbus")
    if gdbus:
        result = subprocess.run(
            [
                gdbus,
                "call",
                "--session",
                "--dest",
                "org.gnome.Shell.Screenshot",
                "--object-path",
                "/org/gnome/Shell/Screenshot",
                "--method",
                "org.gnome.Shell.Screenshot.Screenshot",
                "false",
                "false",
                str(image),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0 and image.exists():
            return
        detail = (result.stderr or result.stdout or "screen capture failed").strip()
        raise ScreenQrError(detail)

    raise ScreenQrError("screen capture is not available on this desktop")


def scan_screen_payloads() -> list[str]:
    """Capture the desktop and decode all QR payloads with zbarimg."""
    zbarimg = shutil.which("zbarimg")
    if not zbarimg:
        raise ScreenQrError("zbarimg is not installed")

    with tempfile.TemporaryDirectory(prefix="ssxng-qr-") as tmp:
        image = Path(tmp) / "screen.png"
        _capture_screen(image)

        decoded = subprocess.run(
            [zbarimg, "--quiet", "--raw", str(image)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
        # zbarimg uses exit 4 when no symbol was found.
        if decoded.returncode not in (0, 4):
            detail = (decoded.stderr or "QR decoding failed").strip()
            raise ScreenQrError(detail)

        seen: set[str] = set()
        payloads: list[str] = []
        for line in decoded.stdout.splitlines():
            value = line.strip()
            if value and value not in seen:
                seen.add(value)
                payloads.append(value)
        return payloads
