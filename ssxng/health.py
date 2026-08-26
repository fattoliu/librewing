from __future__ import annotations

import shutil
import socket
from dataclasses import dataclass

from .config import AppConfig
from .plugins import resolve_plugin


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _command(name: str) -> CheckResult:
    path = shutil.which(name)
    return CheckResult(name, bool(path), path or "not installed")


def _port_free(name: str, port: int) -> CheckResult:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", int(port)))
        return CheckResult(name, True, f"127.0.0.1:{port} available")
    except OSError as exc:
        return CheckResult(name, False, f"127.0.0.1:{port} unavailable: {exc}")
    finally:
        sock.close()


def run_health_checks(config: AppConfig) -> list[CheckResult]:
    results = [
        _command("ss-local"),
        _command("privoxy"),
        _command("gsettings"),
        _port_free("SOCKS port", config.profile.local_port),
        _port_free("HTTP proxy port", config.http_port),
        _port_free("PAC port", config.pac_port),
    ]
    if config.profile.plugin:
        try:
            plugin = resolve_plugin(config.profile.plugin)
            results.append(CheckResult("SIP003 plugin", True, plugin))
        except ValueError as exc:
            results.append(CheckResult("SIP003 plugin", False, str(exc)))
    else:
        results.append(CheckResult("SIP003 plugin", True, "not configured"))
    if config.pac_port == config.http_port:
        results.append(CheckResult("Proxy port separation", False, "PAC and HTTP proxy ports are identical"))
    else:
        results.append(CheckResult("Proxy port separation", True, "PAC and HTTP proxy ports are distinct"))
    return results


def format_health_report(results: list[CheckResult]) -> str:
    return "\n".join(f"{'OK' if item.ok else 'FAIL'}  {item.name}: {item.detail}" for item in results)
