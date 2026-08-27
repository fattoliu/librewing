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


def _socks_port(name: str, port: int) -> CheckResult:
    """Treat a free SOCKS port or a live SOCKS5 listener as healthy.

    `ssx-ng-tool health` can be run either before the desktop client starts or
    while it is already running. A simple bind check incorrectly reports the
    latter as a conflict, so probe the SOCKS5 greeting when the port is busy.
    """
    free = _port_free(name, port)
    if free.ok:
        return free

    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.5) as sock:
            sock.settimeout(0.5)
            sock.sendall(b"\x05\x01\x00")
            reply = sock.recv(2)
            if reply == b"\x05\x00":
                return CheckResult(name, True, f"127.0.0.1:{port} listening (SOCKS5)")
    except OSError:
        pass

    return free


def _service_port(name: str, port: int) -> CheckResult:
    """Treat a free port or an already-listening local service as healthy."""
    free = _port_free(name, port)
    if free.ok:
        return free
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.3):
            return CheckResult(name, True, f"127.0.0.1:{port} listening")
    except OSError:
        return free


def run_health_checks(config: AppConfig) -> list[CheckResult]:
    results = [
        _command("ss-local"),
        _command("gsettings"),
        _socks_port("SOCKS port", config.profile.local_port),
        _service_port("HTTP proxy port", config.http_port),
        _service_port("PAC port", config.pac_port),
    ]
    if config.profile.plugin:
        try:
            plugin = resolve_plugin(config.profile.plugin)
            results.append(CheckResult("SIP003 plugin", True, plugin))
        except ValueError as exc:
            results.append(CheckResult("SIP003 plugin", False, str(exc)))
    else:
        results.append(CheckResult("SIP003 plugin", True, "not configured"))
    return results


def format_health_report(results: list[CheckResult]) -> str:
    return "\n".join(f"{'OK' if item.ok else 'FAIL'}  {item.name}: {item.detail}" for item in results)
