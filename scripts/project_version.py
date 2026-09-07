#!/usr/bin/env python3
"""Read the canonical project version and render release/package forms."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def versions(pyproject: Path) -> dict[str, str]:
    text = pyproject.read_text(encoding="utf-8")
    found = re.search(r'^version = "(\d+\.\d+\.\d+)(?:rc(\d+))?"$', text, re.MULTILINE)
    if found is None:
        raise ValueError("pyproject.toml must contain a final or rc PEP 440 version")
    base, candidate = found.groups()
    python_version = found.group(0).split('"', 2)[1]
    if candidate is None:
        return {"python": python_version, "release": base, "debian": base}
    return {
        "python": python_version,
        "release": f"{base}-rc.{candidate}",
        "debian": f"{base}~rc.{candidate}",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("python", "release", "debian"), default="python")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(versions(root / "pyproject.toml")[args.format])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
