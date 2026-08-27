from ssxng.config import AppConfig, ServerProfile
from ssxng.core import SystemProxy


def test_global_mode_clears_stale_http_proxies(monkeypatch, tmp_path):
    cfg = AppConfig(profiles=[ServerProfile(server="example.com", password="x", local_port=1080)])
    calls = []

    monkeypatch.setattr(cfg, "save", lambda: None)
    monkeypatch.setattr(SystemProxy, "_gsettings", staticmethod(lambda schema, key, value: calls.append((schema, key, value))))

    SystemProxy(cfg).global_mode()

    assert ("org.gnome.system.proxy.http", "host", "''") in calls
    assert ("org.gnome.system.proxy.http", "port", "0") in calls
    assert ("org.gnome.system.proxy.https", "host", "''") in calls
    assert ("org.gnome.system.proxy.https", "port", "0") in calls
    assert ("org.gnome.system.proxy.socks", "host", "'127.0.0.1'") in calls
    assert ("org.gnome.system.proxy.socks", "port", "1080") in calls
    assert calls[-1] == ("org.gnome.system.proxy", "mode", "'manual'")
    assert cfg.mode == "global"
