import base64

import pytest

from ssxng import pac
from ssxng.config import AppConfig, ServerProfile


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
    assert '"google.com"' in result
    assert '"mail.google.com"' in result
    assert f"SOCKS5 127.0.0.1:{config.profile.local_port}" in result
    assert "domainMatches(directDomains, host)" in result
    assert result.index("domainMatches(directDomains, host)") < result.index("domainMatches(proxyDomains, host)")


def test_global_pac_proxies_everything_except_local_hosts():
    config = AppConfig(profiles=[ServerProfile(server="example.com", password="x", local_port=1080)])
    result = pac.build_global_pac(config)
    assert 'return "DIRECT";' in result
    assert 'return "SOCKS5 127.0.0.1:1080; DIRECT";' in result


def test_global_pac_uses_configured_listener():
    config = AppConfig(socks_listen_address="192.0.2.10")
    assert "SOCKS5 192.0.2.10:1080" in pac.build_global_pac(config)

    config.socks_listen_address = "::"
    assert "SOCKS5 [::1]:1080" in pac.build_global_pac(config)


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
        custom_rules=["google.com", "||custom.example", "@@mail.google.com"],
        profiles=[ServerProfile(server="example.com", password="x")],
    )
    rules = pac.merged_abp_rules(config)
    assert rules[:3] == ["google.com", "||custom.example", "@@mail.google.com"]
    assert "||google.com" not in rules
    assert "|https://example.com/path*" in rules
    assert "@@||direct.example.com" in rules
    assert "/blocked-[0-9]+/" in rules


def test_compact_pac_contains_gfwlist_domains_and_whitelist(tmp_path, monkeypatch):
    raw = "\n".join(
        [
            "[AutoProxy 0.2.9]",
            "||google.com",
            "||youtube.com",
            "@@||dl.google.com",
            "! comment",
        ]
    ).encode()
    gfw_path = tmp_path / "gfwlist.txt"
    gfw_path.write_bytes(base64.b64encode(raw))
    monkeypatch.setattr(pac, "GFWLIST_FILE", gfw_path)
    config = AppConfig(
        gfwlist_enabled=True,
        profiles=[ServerProfile(server="example.com", password="x", local_port=1080)],
    )
    result = pac.build_pac(config)
    assert result.startswith("// ShadowsocksX-NG Linux compact PAC")
    assert '"google.com"' in result
    assert '"youtube.com"' in result
    assert '"dl.google.com"' in result
    assert 'return "SOCKS5 127.0.0.1:1080; DIRECT";' in result
    assert "function contains(sorted, value)" in result
    assert "function domainMatches(sorted, host)" in result


def test_compact_pac_does_not_embed_legacy_abp_runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(pac, "GFWLIST_FILE", tmp_path / "gfwlist.txt")
    config = AppConfig(
        custom_rules=["||google.com"],
        gfwlist_enabled=False,
        profiles=[ServerProfile(server="example.com", password="x")],
    )
    result = pac.build_pac(config)
    assert "defaultMatcher" not in result
    assert "Filter.fromText" not in result
    assert "__RULES__" not in result


def test_rule_updates_require_https_before_network_access(monkeypatch):
    config = AppConfig(gfwlist_url="http://example.com/gfwlist.txt")
    monkeypatch.setattr(pac, "_download", lambda *_args, **_kwargs: pytest.fail("must not download"))

    with pytest.raises(ValueError, match="GFWList URL must be a valid HTTPS URL"):
        pac.update_gfwlist(config)


def test_rule_download_rejects_oversized_response(monkeypatch):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _size):
            return b"x" * (pac.MAX_RULE_DOWNLOAD_BYTES + 1)

    monkeypatch.setattr(pac.shutil, "which", lambda _name: None)
    monkeypatch.setattr(pac.urllib.request, "urlopen", lambda *_args, **_kwargs: Response())

    with pytest.raises(ValueError, match="too large"):
        pac._download("https://example.com/rules")
