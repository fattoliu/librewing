from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .config import ServerProfile, write_private_text

FORMAT = "librewing-servers"
VERSION = 1


def export_servers(profiles: list[ServerProfile], output: Path) -> Path:
    output = Path(output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": FORMAT,
        "version": VERSION,
        "servers": [asdict(profile) for profile in profiles],
    }
    write_private_text(output, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return output


def load_servers(path: Path) -> list[ServerProfile]:
    path = Path(path).expanduser()
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        raw_servers = data
    elif isinstance(data, dict):
        raw_servers = data.get("servers", [])
    else:
        raise ValueError("Server configuration must be a JSON object or array")
    if not isinstance(raw_servers, list):
        raise ValueError("servers must be a JSON array")
    profiles = [ServerProfile.from_dict(item) for item in raw_servers if isinstance(item, dict)]
    profiles = [profile for profile in profiles if profile.server]
    if not profiles:
        raise ValueError("No valid server profiles found")
    return profiles


def example_json() -> str:
    example = ServerProfile(
        name="Example",
        server="example.com",
        server_port=8388,
        password="password",
        method="aes-256-gcm",
        plugin="/usr/local/bin/obfs-local",
        plugin_opts="obfs=tls",
        local_port=1080,
    )
    return json.dumps(
        {"format": FORMAT, "version": VERSION, "servers": [asdict(example)]},
        ensure_ascii=False,
        indent=2,
    ) + "\n"
