from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .share import build_ss_url, parse_ss_url
from .config import ServerProfile


def _require(command: str) -> str:
    path = shutil.which(command)
    if not path:
        raise RuntimeError(f"{command} is not installed")
    return path


def export_profile_qr(profile: ServerProfile, output: Path) -> Path:
    """Render an ss:// profile into a PNG QR code using qrencode."""
    executable = _require("qrencode")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=output.parent,
    )
    temporary = Path(temporary_name)
    os.close(descriptor)
    try:
        result = subprocess.run(
            [executable, "-o", str(temporary), "-s", "8", "-m", "2", build_ss_url(profile)],
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "qrencode failed")
        if not temporary.exists():
            raise RuntimeError("qrencode did not create the output file")
        os.chmod(temporary, 0o600)
        os.replace(temporary, output)
        os.chmod(output, 0o600)
        return output
    finally:
        temporary.unlink(missing_ok=True)


def scan_profile_qr(image: Path) -> ServerProfile:
    """Decode the first ss:// QR code in an image using zbarimg."""
    executable = _require("zbarimg")
    image = Path(image)
    if not image.is_file():
        raise FileNotFoundError(image)
    result = subprocess.run(
        [executable, "--quiet", "--raw", str(image)],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "No QR code found")
    for line in result.stdout.splitlines():
        value = line.strip()
        if value.lower().startswith("ss://"):
            return parse_ss_url(value)
    raise ValueError("QR code does not contain an ss:// server link")
