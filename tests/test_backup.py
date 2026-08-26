import json
import stat

import pytest

from ssxng.backup import BackupError, export_backup, load_backup
from ssxng.config import AppConfig, ServerProfile


def test_backup_roundtrip_preserves_profiles_and_credentials(tmp_path):
    cfg = AppConfig(
        mode="pac",
        active_profile=1,
        custom_rules=["||example.com", "@@cn.example.com"],
        profiles=[
            ServerProfile(name="A", server="a.example", password="one"),
            ServerProfile(name="B", server="b.example", server_port=443, password="two", plugin="obfs-local"),
        ],
    )
    path = export_backup(cfg, tmp_path / "backup.json")
    restored = load_backup(path)
    assert restored.mode == "pac"
    assert restored.active_profile == 1
    assert restored.profile.name == "B"
    assert restored.profile.password == "two"
    assert restored.custom_rules == cfg.custom_rules


def test_backup_file_is_private(tmp_path):
    path = export_backup(AppConfig(), tmp_path / "backup.json")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_rejects_unknown_backup_format(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"format": "other", "version": 1, "config": {}}), encoding="utf-8")
    with pytest.raises(BackupError, match="Not a ShadowsocksX-NG Linux backup"):
        load_backup(path)


def test_rejects_empty_profiles(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps({"format": "shadowsocksx-ng-linux-backup", "version": 1, "config": {"profiles": []}}),
        encoding="utf-8",
    )
    with pytest.raises(BackupError, match="at least one server profile"):
        load_backup(path)
