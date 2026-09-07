import importlib.util
from pathlib import Path


SCRIPT = Path("scripts/generate-sbom.py")
SPEC = importlib.util.spec_from_file_location("generate_sbom", SCRIPT)
assert SPEC and SPEC.loader
generate_sbom = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_sbom)


def test_spdx_document_is_deterministic_and_describes_all_files(tmp_path):
    root = tmp_path / "root"
    (root / "usr/bin").mkdir(parents=True)
    (root / "usr/bin/app").write_bytes(b"application")
    (root / "usr/share/doc").mkdir(parents=True)
    (root / "usr/share/doc/LICENSE").write_bytes(b"GPL")
    args = {
        "package_name": "librewing",
        "version": "1.2.3",
        "architecture": "amd64",
        "package_checksum": "a" * 64,
        "source_date_epoch": 1_700_000_000,
    }

    first = generate_sbom.build_document(root, **args)
    second = generate_sbom.build_document(root, **args)

    assert first == second
    assert first["spdxVersion"] == "SPDX-2.3"
    assert first["creationInfo"]["created"] == "2023-11-14T22:13:20Z"
    assert [item["fileName"] for item in first["files"]] == [
        "/usr/bin/app",
        "/usr/share/doc/LICENSE",
    ]
    assert first["packages"][0]["checksums"][0]["checksumValue"] == "a" * 64
    contains = [
        item for item in first["relationships"] if item["relationshipType"] == "CONTAINS"
    ]
    assert len(contains) == 2
