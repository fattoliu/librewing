#!/usr/bin/env python3
"""Generate a deterministic SPDX 2.3 SBOM for a Debian package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deb_field(package: Path, field: str) -> str:
    return subprocess.run(
        ["dpkg-deb", "--field", str(package), field],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def build_document(
    root: Path,
    *,
    package_name: str,
    version: str,
    architecture: str,
    package_checksum: str,
    source_date_epoch: int,
) -> dict[str, object]:
    files = []
    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": "SPDXRef-Package",
        }
    ]
    for index, path in enumerate(sorted(item for item in root.rglob("*") if item.is_file()), 1):
        spdx_id = f"SPDXRef-File-{index}"
        files.append(
            {
                "SPDXID": spdx_id,
                "fileName": "/" + path.relative_to(root).as_posix(),
                "checksums": [{"algorithm": "SHA256", "checksumValue": sha256(path)}],
                "licenseConcluded": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-Package",
                "relationshipType": "CONTAINS",
                "relatedSpdxElement": spdx_id,
            }
        )

    created = datetime.fromtimestamp(source_date_epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    namespace = (
        "https://github.com/fattoliu/librewing/spdx/"
        f"{package_name}-{version}-{architecture}-{package_checksum}"
    )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{package_name}_{version}_{architecture}",
        "documentNamespace": namespace,
        "creationInfo": {
            "created": created,
            "creators": ["Tool: librewing-generate-sbom"],
        },
        "packages": [
            {
                "SPDXID": "SPDXRef-Package",
                "name": package_name,
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": True,
                "licenseConcluded": "GPL-3.0-or-later",
                "licenseDeclared": "GPL-3.0-or-later",
                "copyrightText": "Copyright (c) LibreWing contributors",
                "checksums": [{"algorithm": "SHA256", "checksumValue": package_checksum}],
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:deb/ubuntu/{package_name}@{version}?arch={architecture}",
                    }
                ],
            }
        ],
        "files": files,
        "relationships": relationships,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-date-epoch", type=int)
    args = parser.parse_args()
    package = args.package.resolve()
    if not package.is_file():
        parser.error(f"package does not exist: {package}")
    epoch = args.source_date_epoch
    if epoch is None:
        value = os.environ.get("SOURCE_DATE_EPOCH")
        if not value:
            parser.error("--source-date-epoch or SOURCE_DATE_EPOCH is required")
        epoch = int(value)
    output = args.output or package.with_suffix(".spdx.json")

    with tempfile.TemporaryDirectory(prefix="ssxng-sbom-") as temporary:
        root = Path(temporary)
        subprocess.run(["dpkg-deb", "--extract", str(package), str(root)], check=True)
        document = build_document(
            root,
            package_name=deb_field(package, "Package"),
            version=deb_field(package, "Version"),
            architecture=deb_field(package, "Architecture"),
            package_checksum=sha256(package),
            source_date_epoch=epoch,
        )
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
