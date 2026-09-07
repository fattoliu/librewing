from ssxng.config import AppConfig, ServerProfile
from ssxng.core import SystemProxy
from ssxng import runtime_ng
from ssxng.runtime_ng import NgSystemProxy


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


def test_pac_url_revision_changes_with_custom_rules(tmp_path, monkeypatch):
    gfwlist = tmp_path / "gfwlist.txt"
    gfwlist.write_text("cached", encoding="utf-8")
    cfg = AppConfig(
        custom_rules=["example.com"],
        gfwlist_enabled=False,
        profiles=[ServerProfile(server="example.com", password="x", local_port=1080)],
    )
    calls = []

    monkeypatch.setattr(runtime_ng, "GFWLIST_FILE", gfwlist)
    monkeypatch.setattr(cfg, "save", lambda: None)
    monkeypatch.setattr(
        NgSystemProxy,
        "_gsettings",
        staticmethod(lambda schema, key, value: calls.append((schema, key, value))),
    )

    proxy = NgSystemProxy(cfg)
    proxy.pac_mode()
    first_url = calls[0][2]
    cfg.custom_rules = ["example.org"]
    calls.clear()
    proxy.pac_mode()

    assert calls[0][2] != first_url
    assert calls[-1] == ("org.gnome.system.proxy", "mode", "'auto'")
