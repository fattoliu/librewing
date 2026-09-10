import sys
from types import SimpleNamespace

from ssxng import launcher


def test_launcher_migrates_state_before_creating_lock(monkeypatch):
    events = []

    class FakeLock:
        def __enter__(self):
            events.append("lock")

        def __exit__(self, _exc_type, _exc, _tb):
            return None

    monkeypatch.setattr(launcher, "migrate_legacy_app_dir", lambda: events.append("migrate"))
    monkeypatch.setattr(launcher, "InstanceLock", FakeLock)
    monkeypatch.setattr(launcher, "cleanup_managed_ss_local", lambda: None)
    monkeypatch.setitem(
        sys.modules,
        "ssxng.app_ng_features",
        SimpleNamespace(main=lambda: 0),
    )

    assert launcher.main() == 0
    assert events == ["migrate", "lock"]
