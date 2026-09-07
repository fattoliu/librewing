from ssxng import autostart
from ssxng.autostart import desktop_entry, is_enabled, set_enabled


def test_desktop_entry_contains_exec():
    entry = desktop_entry("/tmp/librewing")
    assert "Exec=/tmp/librewing" in entry
    assert "X-GNOME-Autostart-enabled=true" in entry


def test_set_enabled_round_trip(tmp_path):
    path = tmp_path / "autostart" / "librewing.desktop"
    assert not is_enabled(path)
    set_enabled(True, "/usr/bin/librewing", path)
    assert is_enabled(path)
    set_enabled(False, path=path)
    assert not path.exists()


def test_default_autostart_migrates_legacy_entry(tmp_path, monkeypatch):
    current = tmp_path / "librewing.desktop"
    legacy = tmp_path / "shadowsocksx-ng-linux.desktop"
    legacy.write_text(desktop_entry("/usr/bin/ssx-ng-linux"), encoding="utf-8")
    monkeypatch.setattr(autostart, "AUTOSTART_FILE", current)
    monkeypatch.setattr(autostart, "LEGACY_AUTOSTART_FILE", legacy)

    assert is_enabled()
    set_enabled(True, "/usr/bin/librewing")

    assert current.exists()
    assert "Exec=/usr/bin/librewing" in current.read_text(encoding="utf-8")
    assert not legacy.exists()
