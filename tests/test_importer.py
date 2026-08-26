from ssxng.config import ServerProfile
from ssxng.importer import extract_ss_urls, import_profiles_from_text
from ssxng.share import build_ss_url


def _profile(name: str, server: str = "example.com") -> ServerProfile:
    return ServerProfile(
        name=name,
        server=server,
        server_port=443,
        password="secret",
        method="aes-256-gcm",
        plugin="obfs-local",
        plugin_opts="obfs=tls",
    )


def test_extract_urls_from_arbitrary_text():
    first = build_ss_url(_profile("One"))
    second = build_ss_url(_profile("Two", "two.example.com"))
    text = f"hello {first}\nanything <{second}> and duplicate {first}"
    assert extract_ss_urls(text) == [first, second]


def test_import_skips_duplicates_and_invalid_urls():
    existing = _profile("Existing")
    duplicate = build_ss_url(existing)
    fresh = build_ss_url(_profile("Fresh", "fresh.example.com"))
    imported = import_profiles_from_text(
        f"{duplicate}\nss://definitely-invalid\n{fresh}",
        [existing],
    )
    assert len(imported) == 1
    assert imported[0].server == "fresh.example.com"
