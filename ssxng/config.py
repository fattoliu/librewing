from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .plugins import resolve_plugin

APP_DIR = Path.home() / ".config" / "shadowsocksx-ng-linux"
CONFIG_FILE = APP_DIR / "config.json"
RUNTIME_FILE = APP_DIR / "runtime.json"
GFWLIST_FILE = APP_DIR / "gfwlist.txt"
ABP_TEMPLATE_FILE = APP_DIR / "abp.js"
LOG_FILE = APP_DIR / "app.log"

DEFAULT_GFWLIST_URL = "https://raw.githubusercontent.com/gfwlist/gfwlist/master/gfwlist.txt"
DEFAULT_ABP_TEMPLATE_URL = "https://raw.githubusercontent.com/shadowsocks/ShadowsocksX-NG/develop/ShadowsocksX-NG/abp.js"
DEFAULT_PROXY_EXCEPTIONS = "127.0.0.1, localhost, 192.168.0.0/16, 10.0.0.0/8, FE80::/64, ::1, FD00::/8"


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
        return cls(**{k: v for k, v in data.items() if k in fields})


@dataclass
class AppConfig:
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
    socks_timeout: int = 60
    udp_relay: bool = True
    verbose_mode: bool = False
    http_enabled: bool = True
    http_listen_address: str = "127.0.0.1"
    pac_bind_localhost: bool = True
    external_pac_url: str = ""
    proxy_exceptions: str = DEFAULT_PROXY_EXCEPTIONS
    show_mode_in_status_bar: bool = True

    profiles: list[ServerProfile] = field(default_factory=lambda: [ServerProfile()])

    @classmethod
    def load(cls) -> AppConfig:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            cfg = cls()
            cfg.save()
            return cfg
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("configuration root must be an object")
            data = dict(raw)
            profile_data = data.pop("profiles", [])
            if not isinstance(profile_data, list):
                raise ValueError("profiles must be a list")
            profiles = [ServerProfile.from_dict(x) for x in profile_data if isinstance(x, dict)]
            cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            if profiles:
                cfg.profiles = profiles
            cfg.active_profile = min(max(int(cfg.active_profile), 0), len(cfg.profiles) - 1)
            changed = False
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
            return backup
        except OSError:
            return None

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        content = json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n"
        temporary = CONFIG_FILE.with_suffix(".json.tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(CONFIG_FILE)

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
        RUNTIME_FILE.write_text(json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return RUNTIME_FILE
