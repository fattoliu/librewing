from ssxng.config import AppConfig, ServerProfile
from ssxng.core import SystemProxy


def test_global_mode_uses_local_global_pac(monkeypatch):
    cfg = AppConfig(profiles=[ServerProfile(server="example.com", password="x", local_port=1080)])
    calls = []

    monkeypatch.setattr(cfg, "save", lambda: None)
    monkeypatch.setattr(SystemProxy, "_gsettings", staticmethod(lambda schema, key, value: calls.append((schema, key, value))))

    SystemProxy(cfg).global_mode()

    assert (
        "org.gnome.system.proxy",
        "autoconfig-url",
        f"'http://127.0.0.1:{cfg.pac_port}/global.pac'",
    ) in calls
    assert calls[-1] == ("org.gnome.system.proxy", "mode", "'auto'")
    assert cfg.mode == "global"
