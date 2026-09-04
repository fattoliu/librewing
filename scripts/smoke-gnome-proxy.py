#!/usr/bin/env python3
"""Exercise the real GNOME proxy schema in an isolated settings backend."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from ssxng.config import AppConfig
from ssxng.core import SystemProxy


def read(key: str) -> str:
    return subprocess.run(
        ["gsettings", "get", "org.gnome.system.proxy", key],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ssxng-gsettings-") as temporary:
        os.environ["GSETTINGS_BACKEND"] = "keyfile"
        os.environ["XDG_CONFIG_HOME"] = str(Path(temporary) / "config")
        config = AppConfig()
        config.save = lambda: None  # type: ignore[method-assign]
        proxy = SystemProxy(config)

        proxy.global_mode()
        assert read("mode") == "'auto'"
        assert read("autoconfig-url") == f"'http://127.0.0.1:{config.pac_port}/global.pac'"
        assert config.mode == "global"

        proxy.pac_mode()
        assert read("mode") == "'auto'"
        assert read("autoconfig-url") == f"'http://127.0.0.1:{config.pac_port}/proxy.pac'"
        assert config.mode == "pac"

        proxy.manual()
        assert read("mode") == "'none'"
        assert config.mode == "manual"

        proxy.off()
        assert read("mode") == "'none'"
        assert config.mode == "off"
    print("isolated GNOME proxy integration OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
