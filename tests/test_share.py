from ssxng.config import ServerProfile
from ssxng.share import build_ss_url, parse_ss_url


def test_ss_url_roundtrip_with_plugin():
    source = ServerProfile(
        name="My VPS",
        server="example.com",
        server_port=443,
        password="p@ss:word",
        method="aes-256-gcm",
        plugin="obfs-local",
        plugin_opts="obfs=tls;obfs-host=www.example.com",
    )
    result = parse_ss_url(build_ss_url(source))
    assert result.name == source.name
    assert result.server == source.server
    assert result.server_port == source.server_port
    assert result.password == source.password
    assert result.method == source.method
    assert result.plugin == source.plugin
    assert result.plugin_opts == source.plugin_opts


def test_legacy_ss_url():
    import base64

    payload = base64.urlsafe_b64encode(b"chacha20-ietf-poly1305:secret@1.2.3.4:8388").decode().rstrip("=")
    profile = parse_ss_url(f"ss://{payload}#Legacy")
    assert profile.name == "Legacy"
    assert profile.server == "1.2.3.4"
    assert profile.server_port == 8388
    assert profile.password == "secret"
