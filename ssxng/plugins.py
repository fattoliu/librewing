from __future__ import annotations

import os
import shutil
from dataclasses import dataclass


KNOWN_PLUGINS = (
    "obfs-local",
    "v2ray-plugin",
    "kcptun-client",
    "xray-plugin",
)


@dataclass(frozen=True)
class PluginInfo:
    name: str
    path: str
    available: bool


def discover_plugins(names: tuple[str, ...] = KNOWN_PLUGINS) -> list[PluginInfo]:
    result: list[PluginInfo] = []
    for name in names:
        path = shutil.which(name)
        result.append(PluginInfo(name=name, path=path or "", available=bool(path)))
    return result


def resolve_plugin(value: str) -> str:
    """Resolve a SIP003 plugin name or absolute path to an executable.

    Empty plugin values are allowed and resolve to an empty string. Relative paths
    containing a slash are intentionally rejected because desktop launch working
    directories are not stable.
    """
    value = value.strip()
    if not value:
        return ""
    if os.path.isabs(value):
        if not os.path.isfile(value):
            raise ValueError(f"Plugin does not exist: {value}")
        if not os.access(value, os.X_OK):
            raise ValueError(f"Plugin is not executable: {value}")
        return value
    if "/" in value:
        raise ValueError("Plugin must be a command in PATH or an absolute executable path")
    path = shutil.which(value)
    if not path:
        raise ValueError(f"Plugin not found in PATH: {value}")
    return path


def plugin_summary() -> str:
    lines = []
    for plugin in discover_plugins():
        if plugin.available:
            lines.append(f"{plugin.name}: {plugin.path}")
        else:
            lines.append(f"{plugin.name}: not installed")
    return "\n".join(lines)
