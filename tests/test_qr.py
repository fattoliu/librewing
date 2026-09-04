from __future__ import annotations

import stat
from pathlib import Path

import pytest

from ssxng import qr
from ssxng.config import ServerProfile


def test_export_profile_qr_requires_qrencode(monkeypatch, tmp_path):
    monkeypatch.setattr(qr.shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="qrencode"):
        qr.export_profile_qr(ServerProfile(server="example.com", password="x"), tmp_path / "server.png")


def test_export_profile_qr_is_private_and_atomic(monkeypatch, tmp_path):
    monkeypatch.setattr(qr.shutil, "which", lambda _name: "/usr/bin/qrencode")

    class Result:
        returncode = 0
        stderr = ""

    def run(args, **_kwargs):
        Path(args[args.index("-o") + 1]).write_bytes(b"png")
        return Result()

    monkeypatch.setattr(qr.subprocess, "run", run)
    output = tmp_path / "server.png"

    assert qr.export_profile_qr(ServerProfile(server="example.com", password="x"), output) == output
    assert output.read_bytes() == b"png"
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert not list(tmp_path.glob(".server.png.*.tmp"))


def test_scan_profile_qr_requires_zbarimg(monkeypatch, tmp_path):
    image = tmp_path / "server.png"
    image.write_bytes(b"x")
    monkeypatch.setattr(qr.shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="zbarimg"):
        qr.scan_profile_qr(image)


def test_scan_profile_qr_parses_ss_url(monkeypatch, tmp_path):
    image = tmp_path / "server.png"
    image.write_bytes(b"x")
    monkeypatch.setattr(qr.shutil, "which", lambda name: f"/usr/bin/{name}")

    class Result:
        returncode = 0
        stdout = "ss://YWVzLTI1Ni1nY206cGFzc0BleGFtcGxlLmNvbTo4Mzg4#Example\n"
        stderr = ""

    monkeypatch.setattr(qr.subprocess, "run", lambda *_args, **_kwargs: Result())
    profile = qr.scan_profile_qr(image)
    assert profile.server == "example.com"
    assert profile.server_port == 8388
    assert profile.name == "Example"
