from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .plugins import resolve_plugin

DEFAULT_APP_DIR = Path.home() / ".config" / "librewing"
LEGACY_APP_DIR = Path.home() / ".config" / "shadowsocksx-ng-linux"
APP_DIR = DEFAULT_APP_DIR
CONFIG_FILE = APP_DIR / "config.json"
RUNTIME_FILE = APP_DIR / "runtime.json"
GFWLIST_FILE = APP_DIR / "gfwlist.txt"
ABP_TEMPLATE_FILE = APP_DIR / "abp.js"
LOG_FILE = APP_DIR / "app.log"

DEFAULT_GFWLIST_URL = "https://raw.githubusercontent.com/gfwlist/gfwlist/master/gfwlist.txt"
DEFAULT_ABP_TEMPLATE_URL = "https://raw.githubusercontent.com/shadowsocks/ShadowsocksX-NG/develop/ShadowsocksX-NG/abp.js"
DEFAULT_PROXY_EXCEPTIONS = "127.0.0.1, localhost, 192.168.0.0/16, 10.0.0.0/8, FE80::/64, ::1, FD00::/8"
CURRENT_CONFIG_VERSION = 1
VALID_MODES = frozenset({"off", "pac", "global", "manual", "external_pac"})


class UnsupportedConfigVersion(RuntimeError):
    """Raised when a newer client configuration must not be overwritten."""


def ensure_private_directory(path: Path) -> None:
    """Create a user-owned state directory and repair permissive modes."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


def migrate_legacy_app_dir() -> bool:
    """Move pre-LibreWing user state once without overwriting newer state."""
    if (
        APP_DIR != DEFAULT_APP_DIR
        or APP_DIR.exists()
        or LEGACY_APP_DIR.is_symlink()
        or not LEGACY_APP_DIR.is_dir()
    ):
        return False
    APP_DIR.parent.mkdir(parents=True, exist_ok=True)
    os.replace(LEGACY_APP_DIR, APP_DIR)
    ensure_private_directory(APP_DIR)
    return True


def write_private_text(path: Path, content: str, *, private_parent: bool = False) -> None:
    """Atomically write owner-only text without changing unrelated directories."""
    path = Path(path)
    if private_parent:
        ensure_private_directory(path.parent)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
        raise


@dataclass
class ServerProfile:
    name: str = "Default"
    server: str = ""
    server_port: int = 8388
    password: str = ""
    method: str = "aes-256-gcm"
    plugin: str = ""
    plugin_opts: str = ""
    local_port: int = 1080

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServerProfile:
        fields = cls.__dataclass_fields__
        values = {k: v for k, v in data.items() if k in fields}
        for key in ("server_port", "local_port"):
            if key in values and not isinstance(values[key], bool):
                values[key] = int(values[key])
        return cls(**values)


@dataclass
class AppConfig:
    config_version: int = CURRENT_CONFIG_VERSION
    mode: str = "off"
    active_profile: int = 0
    pac_port: int = 8090
    http_port: int = 1087
    autostart: bool = True
    custom_rules: list[str] = field(default_factory=list)
    gfwlist_url: str = DEFAULT_GFWLIST_URL
    abp_template_url: str = DEFAULT_ABP_TEMPLATE_URL
    gfwlist_enabled: bool = True
    gfwlist_updated_at: str = ""

    # Mirrors the useful parts of ShadowsocksX-NG's Advanced/HTTP/PAC prefs.
    socks_listen_address: str = "127.0.0.1"
    socks_allow_lan: bool = False
    socks_timeout: int = 60
    udp_relay: bool = True
    verbose_mode: bool = False
    http_enabled: bool = True
    http_listen_address: str = "127.0.0.1"
    http_allow_lan: bool = False
    pac_bind_localhost: bool = True
    external_pac_url: str = ""
    proxy_exceptions: str = DEFAULT_PROXY_EXCEPTIONS
    show_mode_in_status_bar: bool = True

    profiles: list[ServerProfile] = field(default_factory=lambda: [ServerProfile()])

    @classmethod
    def load(cls) -> AppConfig:
        migrate_legacy_app_dir()
        ensure_private_directory(APP_DIR)
        if not CONFIG_FILE.exists():
            cfg = cls()
            cfg.save()
            return cfg
        os.chmod(CONFIG_FILE, 0o600)
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("configuration root must be an object")
            data = dict(raw)
            raw_version = data.get("config_version", 0)
            if isinstance(raw_version, bool):
                raise ValueError("config_version must be an integer")
            config_version = int(raw_version)
            if config_version > CURRENT_CONFIG_VERSION:
                raise UnsupportedConfigVersion(
                    f"Configuration version {config_version} requires a newer LibreWing release"
                )
            if config_version < 0:
                raise ValueError("config_version must not be negative")
            changed = config_version != CURRENT_CONFIG_VERSION
            data["config_version"] = CURRENT_CONFIG_VERSION
            profile_data = data.pop("profiles", [])
            if not isinstance(profile_data, list):
                raise ValueError("profiles must be a list")
            profiles = [ServerProfile.from_dict(x) for x in profile_data if isinstance(x, dict)]
            cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            if profiles:
                cfg.profiles = profiles
            cfg.active_profile = min(max(int(cfg.active_profile), 0), len(cfg.profiles) - 1)
            cfg.validate()
            if int(cfg.http_port) == 8119:
                cfg.http_port = 1087
                changed = True
            if changed:
                cfg.save()
            return cfg
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            cls._backup_invalid_config()
            cfg = cls()
            cfg.save()
            return cfg

    @staticmethod
    def _backup_invalid_config() -> Path | None:
        if not CONFIG_FILE.exists():
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = CONFIG_FILE.with_name(f"config.invalid-{stamp}.json")
        try:
            shutil.copy2(CONFIG_FILE, backup)
            os.chmod(backup, 0o600)
            return backup
        except OSError:
            return None

    def save(self) -> None:
        self.validate()
        content = json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n"
        write_private_text(CONFIG_FILE, content, private_parent=True)

    def validate(self) -> None:
        if isinstance(self.config_version, bool) or self.config_version != CURRENT_CONFIG_VERSION:
            raise ValueError(f"config_version must be {CURRENT_CONFIG_VERSION}")
        if self.mode not in VALID_MODES:
            raise ValueError(f"unsupported proxy mode: {self.mode!r}")
        if not self.profiles:
            raise ValueError("at least one server profile is required")
        if (
            isinstance(self.active_profile, bool)
            or not isinstance(self.active_profile, int)
            or not 0 <= self.active_profile < len(self.profiles)
        ):
            raise ValueError("active_profile is outside the server profile list")

        ports = {
            "PAC": self.pac_port,
            "HTTP": self.http_port,
        }
        for name, port in ports.items():
            if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
                raise ValueError(f"{name} port must be an integer from 1 to 65535")
        if isinstance(self.socks_timeout, bool) or not isinstance(self.socks_timeout, int):
            raise ValueError("SOCKS timeout must be an integer")
        if not 1 <= self.socks_timeout <= 86400:
            raise ValueError("SOCKS timeout must be from 1 to 86400 seconds")
        if not isinstance(self.custom_rules, list) or not all(
            isinstance(rule, str) for rule in self.custom_rules
        ):
            raise ValueError("custom_rules must be a list of strings")

        bool_fields = (
            "autostart",
            "gfwlist_enabled",
            "socks_allow_lan",
            "udp_relay",
            "verbose_mode",
            "http_enabled",
            "http_allow_lan",
            "pac_bind_localhost",
            "show_mode_in_status_bar",
        )
        if any(not isinstance(getattr(self, field_name), bool) for field_name in bool_fields):
            raise ValueError("boolean preferences must contain true or false")

        text_fields = (
            "gfwlist_url",
            "abp_template_url",
            "gfwlist_updated_at",
            "socks_listen_address",
            "http_listen_address",
            "external_pac_url",
            "proxy_exceptions",
        )
        if any(not isinstance(getattr(self, field_name), str) for field_name in text_fields):
            raise ValueError("text preferences must contain strings")

        for profile in self.profiles:
            for field_name in ("name", "server", "password", "method", "plugin", "plugin_opts"):
                if not isinstance(getattr(profile, field_name), str):
                    raise ValueError(f"server profile {field_name} must be a string")
            for name, port in (("server", profile.server_port), ("local SOCKS", profile.local_port)):
                if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
                    raise ValueError(f"{name} port must be an integer from 1 to 65535")
        used_ports = [self.pac_port, self.http_port, self.profile.local_port]
        if len(used_ports) != len(set(used_ports)):
            raise ValueError("PAC, HTTP, and local SOCKS ports must be different")

    @property
    def profile(self) -> ServerProfile:
        return self.profiles[self.active_profile]

    def write_runtime(self) -> Path:
        p = self.profile
        runtime: dict[str, Any] = {
            "server": p.server,
            "server_port": int(p.server_port),
            "local_address": self.socks_listen_address or "127.0.0.1",
            "local_port": int(p.local_port),
            "password": p.password,
            "timeout": max(1, int(self.socks_timeout)),
            "method": p.method,
            "mode": "tcp_and_udp" if self.udp_relay else "tcp_only",
        }
        if p.plugin:
            runtime["plugin"] = resolve_plugin(p.plugin)
        if p.plugin_opts:
            runtime["plugin_opts"] = p.plugin_opts
        write_private_text(
            RUNTIME_FILE,
            json.dumps(runtime, ensure_ascii=False, indent=2) + "\n",
            private_parent=True,
        )
        return RUNTIME_FILE
