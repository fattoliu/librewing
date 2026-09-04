from __future__ import annotations

import re
from pathlib import Path

from ssxng import __version__


def test_release_candidate_version_is_consistent():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    build_script = Path("scripts/build-deb.sh").read_text(encoding="utf-8")
    metadata = Path("packaging/io.github.fattoliu.shadowsocksxng.metainfo.xml").read_text(
        encoding="utf-8"
    )

    project_version = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    deb_version = re.search(r'VERSION="\$\{VERSION:-([^}]+)\}"', build_script)
    assert project_version and project_version.group(1) == __version__ == "0.3.0rc1"
    assert deb_version and deb_version.group(1) == "0.3.0~rc.1"
    assert '<release version="0.3.0-rc.1"' in metadata
