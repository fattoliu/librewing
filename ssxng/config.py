from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .plugins import resolve_plugin

APP_DIR = Path.home() / ".config" / "shadowsocksx-ng-linux"
CONFIG_FILE = APP_DIR / "config.json"
RUNTIME_FILE = APP_DIR / "runtime.json"
GFWLIST_FILE = APP_DIR / "gfwlist.txt"
ABP_TEMPLATE_FILE = APP_DIR / "abp.js"
PRIVOXY_CONFIG_FILE = APP_DIR / "privoxy.conf"
LOG_FILE = APP_DIR / "app.log"

DEFAULT_GFWLIST_URL = "https://raw.githubusercontent.com/gfwlist/gfwlist/master/gfwlist.txt"
DEFAULT_ABP_TEMPLATE_URL = "https://raw.githubusercontent.com/shadowsocks/ShadowsocksX-NG/develop/ShadowsocksX-NG/abp.js"


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
    def from_dict(cls, data: dict[str, Any]) -> "ServerProfile":
        fields = cls.__dataclass_fields__
        return cls(**{k: v for k, v in data.items() if k in fields})


@dataclass
class AppConfig:
    mode: str = "off"
    active_profile: int = 0
    pac_port: int = 8090
    http_port: int = 8119
    autostart: bool = True
    custom_rules: list[str] = field(default_factory=list)
    gfwlist_url: str = DEFAULT_GFWLIST_URL
    abp_template_url: str = DEFAULT_ABP_TEMPLATE_URL
    gfwlist_enabled: bool = True
    gfwlist_updated_at: str = ""
    profiles: list[ServerProfile] = field(default_factory=lambda: [ServerProfile()])

    @classmethod
    def load(cls) -> "AppConfig":
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if not CONFIG_FILE.exists():
            cfg = cls()
            cfg.save()
            return cfg
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        profiles = [ServerProfile.from_dict(x) for x in data.pop("profiles", [])]
        cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        if profiles:
            cfg.profiles = profiles
        cfg.active_profile = min(max(cfg.active_profile, 0), len(cfg.profiles) - 1)
        return cfg

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def profile(self) -> ServerProfile:
        return self.profiles[self.active_profile]

    def write_runtime(self) -> Path:
        p = self.profile
        runtime: dict[str, Any] = {
            "server": p.server,
            "server_port": int(p.server_port),
            "local_address": "127.0.0.1",
            "local_port": int(p.local_port),
            "password": p.password,
            "timeout": 300,
            "method": p.method,
            "mode": "tcp_and_udp",
        }
        if p.plugin:
            # Resolve early so users get a clear error instead of a cryptic ss-local
            # child-process failure when a SIP003 plugin is missing or not executable.
            runtime["plugin"] = resolve_plugin(p.plugin)
        if p.plugin_opts:
            runtime["plugin_opts"] = p.plugin_opts
        RUNTIME_FILE.write_text(json.dumps(runtime, ensure_ascii=False, indent=2), encoding="utf-8")
        return RUNTIME_FILE
