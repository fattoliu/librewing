from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


class ScreenQrError(RuntimeError):
    pass


def scan_screen_payloads() -> list[str]:
    """Capture the desktop and decode QR payloads with zbarimg.

    Ubuntu/GNOME's gnome-screenshot is used rather than reading the framebuffer
    directly so the implementation remains compatible with modern Wayland
    sessions. zbarimg is already a runtime dependency of the client.
    """
    screenshot = shutil.which("gnome-screenshot")
    zbarimg = shutil.which("zbarimg")
    if not screenshot:
        raise ScreenQrError("gnome-screenshot is not installed")
    if not zbarimg:
        raise ScreenQrError("zbarimg is not installed")

    with tempfile.TemporaryDirectory(prefix="ssxng-qr-") as tmp:
        image = Path(tmp) / "screen.png"
        capture = subprocess.run(
            [screenshot, "-f", str(image)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
            check=False,
        )
        if capture.returncode != 0 or not image.exists():
            detail = (capture.stderr or capture.stdout or "screen capture failed").strip()
            raise ScreenQrError(detail)

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
