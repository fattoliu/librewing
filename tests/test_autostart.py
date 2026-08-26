from ssxng.autostart import desktop_entry, is_enabled, set_enabled


def test_desktop_entry_contains_exec():
    entry = desktop_entry("/tmp/ssx-ng-linux")
    assert "Exec=/tmp/ssx-ng-linux" in entry
    assert "X-GNOME-Autostart-enabled=true" in entry


def test_set_enabled_round_trip(tmp_path):
    path = tmp_path / "autostart" / "shadowsocksx-ng-linux.desktop"
    assert not is_enabled(path)
    set_enabled(True, "/usr/bin/ssx-ng-linux", path)
    assert is_enabled(path)
    set_enabled(False, path=path)
    assert not path.exists()
