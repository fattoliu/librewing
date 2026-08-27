from __future__ import annotations

import pytest

from ssxng import qr
from ssxng.config import ServerProfile


def test_export_profile_qr_requires_qrencode(monkeypatch, tmp_path):
    monkeypatch.setattr(qr.shutil, "which", lambda _name: None)
    with pytest.raises(RuntimeError, match="qrencode"):
        qr.export_profile_qr(ServerProfile(server="example.com", password="x"), tmp_path / "server.png")


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
