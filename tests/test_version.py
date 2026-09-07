from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from ssxng import __version__


def test_release_candidate_version_is_consistent():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    metadata = Path("packaging/io.github.fattoliu.shadowsocksxng.metainfo.xml").read_text(
        encoding="utf-8"
    )

    project_version = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    assert project_version and project_version.group(1) == __version__ == "0.3.0rc2"
    assert '<release version="0.3.0-rc.2"' in metadata

    script = Path("scripts/project_version.py")
    rendered = {
        kind: subprocess.run(
            [sys.executable, script, "--format", kind],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        for kind in ("python", "release", "debian")
    }
    assert rendered == {
        "python": "0.3.0rc2",
        "release": "0.3.0-rc.2",
        "debian": "0.3.0~rc.2",
    }
