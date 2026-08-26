import base64

from ssxng.config import AppConfig, ServerProfile
from ssxng import pac


def test_parse_gfwlist_domains():
    raw = "\n".join(["||google.com", "||youtube.com", "! comment", "@@||example.com"]).encode()
    encoded = base64.b64encode(raw)
    domains = pac.parse_gfwlist(encoded)
    assert "google.com" in domains
    assert "youtube.com" in domains
    assert "example.com" not in domains


def test_custom_direct_rule_precedes_proxy(tmp_path, monkeypatch):
    monkeypatch.setattr(pac, "GFWLIST_FILE", tmp_path / "gfwlist.txt")
    config = AppConfig(
        custom_rules=["google.com", "@@mail.google.com"],
        gfwlist_enabled=False,
        profiles=[ServerProfile(server="example.com", password="x")],
    )
    result = pac.build_pac(config)
    assert 'dnsDomainIs(host, "mail.google.com")' in result
    assert 'dnsDomainIs(host, "google.com")' in result
    assert f"PROXY 127.0.0.1:{config.http_port}" in result
