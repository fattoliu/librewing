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
    monkeypatch.setattr(pac, "ABP_TEMPLATE_FILE", tmp_path / "abp.js")
    config = AppConfig(
        custom_rules=["google.com", "@@mail.google.com"],
        gfwlist_enabled=False,
        profiles=[ServerProfile(server="example.com", password="x")],
    )
    result = pac.build_pac(config)
    assert 'dnsDomainIs(host, "mail.google.com")' in result
    assert 'dnsDomainIs(host, "google.com")' in result
    assert f"PROXY 127.0.0.1:{config.http_port}" in result


def test_abp_rules_preserve_complex_upstream_syntax(tmp_path, monkeypatch):
    gfwlist = "\n".join(
        [
            "[AutoProxy 0.2.9]",
            "! comment",
            "||google.com",
            "|https://example.com/path*",
            "@@||direct.example.com",
            "/blocked-[0-9]+/",
        ]
    ).encode()
    gfw_path = tmp_path / "gfwlist.txt"
    gfw_path.write_bytes(base64.b64encode(gfwlist))
    monkeypatch.setattr(pac, "GFWLIST_FILE", gfw_path)
    config = AppConfig(
        custom_rules=["@@google.com", "||custom.example"],
        profiles=[ServerProfile(server="example.com", password="x")],
    )
    rules = pac.merged_abp_rules(config)
    assert rules[:2] == ["@@google.com", "||custom.example"]
    assert "||google.com" not in rules
    assert "|https://example.com/path*" in rules
    assert "@@||direct.example.com" in rules
    assert "/blocked-[0-9]+/" in rules


def test_build_pac_uses_cached_upstream_template(tmp_path, monkeypatch):
    gfw_path = tmp_path / "gfwlist.txt"
    gfw_path.write_bytes(base64.b64encode(b"||google.com\n"))
    template_path = tmp_path / "abp.js"
    template_path.write_text(
        'var proxy = "SOCKS5 __SOCKS5ADDR__:__SOCKS5PORT__; SOCKS __SOCKS5ADDR__:__SOCKS5PORT__; DIRECT;";\n'
        "var rules = __RULES__;\n"
        "function FindProxyForURL(url, host) { return proxy; }\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(pac, "GFWLIST_FILE", gfw_path)
    monkeypatch.setattr(pac, "ABP_TEMPLATE_FILE", template_path)
    config = AppConfig(profiles=[ServerProfile(server="example.com", password="x")])
    result = pac.build_pac(config)
    assert f'var proxy = "PROXY 127.0.0.1:{config.http_port}; DIRECT;";' in result
    assert '"||google.com"' in result
    assert "__RULES__" not in result
