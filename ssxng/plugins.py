from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


BUNDLED_BIN_DIR = Path("/usr/lib/shadowsocksx-ng-linux/bin")
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


class PluginList(list[PluginInfo]):
    """Plugin discovery result with a small mapping-style compatibility API.

    Iteration/indexing still exposes every known plugin, while ``items()`` and
    truth testing only consider installed plugins. This keeps diagnostics useful
    without forcing UI callers to duplicate filtering logic.
    """

    def items(self) -> list[tuple[str, str]]:
        return [(plugin.name, plugin.path) for plugin in self if plugin.available]

    def __bool__(self) -> bool:
        return any(plugin.available for plugin in self)

    @property
    def available_count(self) -> int:
        return sum(1 for plugin in self if plugin.available)


def bundled_executable(name: str) -> str:
    """Return an executable shipped inside the application package, if present."""
    candidate = BUNDLED_BIN_DIR / name
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return ""


def find_plugin(name: str) -> str:
    """Prefer the application-bundled plugin, then fall back to the system PATH."""
    return bundled_executable(name) or shutil.which(name) or ""


def default_plugin_value(name: str = "obfs-local") -> str:
    """Return a portable plugin value for new profiles when that plugin exists."""
    return name if find_plugin(name) else ""


def discover_plugins(names: tuple[str, ...] = KNOWN_PLUGINS) -> PluginList:
    result = PluginList()
    for name in names:
        path = find_plugin(name)
        result.append(PluginInfo(name=name, path=path, available=bool(path)))
    return result


def resolve_plugin(value: str) -> str:
    """Resolve a SIP003 plugin name or absolute path to an executable.

    Empty plugin values are allowed and resolve to an empty string. Bare command
    names first resolve against binaries bundled with ShadowsocksX-NG Linux, then
    against PATH. Relative paths containing a slash are rejected because desktop
    launch working directories are not stable.
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
    path = find_plugin(value)
    if not path:
        raise ValueError(f"Plugin not found: {value}")
    return path


def plugin_summary() -> str:
    lines = []
    for plugin in discover_plugins():
        if plugin.available:
            lines.append(f"{plugin.name}: {plugin.path}")
        else:
            lines.append(f"{plugin.name}: not installed")
    return "\n".join(lines)
