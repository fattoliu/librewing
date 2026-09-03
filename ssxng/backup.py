from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .config import AppConfig, ServerProfile, write_private_text


class BackupError(ValueError):
    pass


def export_backup(config: AppConfig, output: Path) -> Path:
    """Export the complete client configuration, including credentials.

    The backup is deliberately permissioned to the current user only because
    Shadowsocks server passwords are part of the file.
    """
    output = Path(output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": "shadowsocksx-ng-linux-backup",
        "version": 1,
        "config": asdict(config),
    }
    write_private_text(output, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return output


def load_backup(path: Path) -> AppConfig:
    path = Path(path).expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError(f"Unable to read backup: {exc}") from exc

    if payload.get("format") != "shadowsocksx-ng-linux-backup":
        raise BackupError("Not a ShadowsocksX-NG Linux backup file")
    if payload.get("version") != 1:
        raise BackupError(f"Unsupported backup version: {payload.get('version')}")

    data = payload.get("config")
    if not isinstance(data, dict):
        raise BackupError("Backup does not contain a valid config object")

    profile_data = data.pop("profiles", None)
    if not isinstance(profile_data, list) or not profile_data:
        raise BackupError("Backup must contain at least one server profile")

    try:
        profiles = [ServerProfile.from_dict(item) for item in profile_data if isinstance(item, dict)]
        cfg = AppConfig(**{k: v for k, v in data.items() if k in AppConfig.__dataclass_fields__})
    except (TypeError, ValueError) as exc:
        raise BackupError(f"Invalid backup configuration: {exc}") from exc

    if not profiles:
        raise BackupError("Backup must contain at least one valid server profile")
    cfg.profiles = profiles
    cfg.active_profile = min(max(int(cfg.active_profile), 0), len(profiles) - 1)
    return cfg


def restore_backup(path: Path) -> AppConfig:
    config = load_backup(path)
    config.save()
    return config
