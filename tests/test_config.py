import json

from ssxng import config


def test_load_recovers_from_invalid_json(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "APP_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    config.CONFIG_FILE.write_text("{not-json", encoding="utf-8")

    loaded = config.AppConfig.load()

    assert loaded.mode == "off"
    assert loaded.profiles
    assert json.loads(config.CONFIG_FILE.read_text(encoding="utf-8"))["mode"] == "off"
    backups = list(tmp_path.glob("config.invalid-*.json"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{not-json"


def test_save_replaces_config_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "APP_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    cfg = config.AppConfig(mode="manual")

    cfg.save()

    assert json.loads(config.CONFIG_FILE.read_text(encoding="utf-8"))["mode"] == "manual"
    assert not (tmp_path / "config.json.tmp").exists()


def test_load_ignores_unknown_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "APP_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    config.CONFIG_FILE.write_text(
        json.dumps({"mode": "pac", "future_option": True, "profiles": [{"name": "A", "unknown": 1}]}),
        encoding="utf-8",
    )

    loaded = config.AppConfig.load()

    assert loaded.mode == "pac"
    assert loaded.profile.name == "A"


def test_load_migrates_legacy_privoxy_port_to_1087(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "APP_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    config.CONFIG_FILE.write_text(
        json.dumps({"http_port": 8119, "profiles": [{"name": "A"}]}),
        encoding="utf-8",
    )

    loaded = config.AppConfig.load()

    assert loaded.http_port == 1087
    assert json.loads(config.CONFIG_FILE.read_text(encoding="utf-8"))["http_port"] == 1087


def test_http_proxy_default_port_matches_ng_convention():
    assert config.AppConfig().http_port == 1087
