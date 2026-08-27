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


def _probe_host(host: str) -> str:
    value = (host or "127.0.0.1").strip()
    if value in ("0.0.0.0", "localhost"):
        return "127.0.0.1"
    if value == "::":
        return "::1"
    return value


def _port_free(name: str, port: int, host: str = "127.0.0.1") -> CheckResult:
    bind_host = (host or "127.0.0.1").strip()
    family = socket.AF_INET6 if ":" in bind_host else socket.AF_INET
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        sock.bind((bind_host, int(port)))
        return CheckResult(name, True, f"{bind_host}:{port} available")
    except OSError as exc:
        return CheckResult(name, False, f"{bind_host}:{port} unavailable: {exc}")
    finally:
        sock.close()


def _socks_port(name: str, port: int, host: str = "127.0.0.1") -> CheckResult:
    """Treat a free SOCKS port or a live SOCKS5 listener as healthy."""
    free = _port_free(name, port, host)
    if free.ok:
        return free

    target = _probe_host(host)
    try:
        with socket.create_connection((target, int(port)), timeout=0.5) as sock:
            sock.settimeout(0.5)
            sock.sendall(b"\x05\x01\x00")
            reply = sock.recv(2)
            if reply == b"\x05\x00":
                return CheckResult(name, True, f"{host}:{port} listening (SOCKS5)")
    except OSError:
        pass

    return free


def _service_port(name: str, port: int, host: str = "127.0.0.1") -> CheckResult:
    """Treat a free port or an already-listening configured service as healthy."""
    free = _port_free(name, port, host)
    if free.ok:
        return free
    target = _probe_host(host)
    try:
        with socket.create_connection((target, int(port)), timeout=0.3):
            return CheckResult(name, True, f"{host}:{port} listening")
    except OSError:
        return free


def run_health_checks(config: AppConfig) -> list[CheckResult]:
    pac_host = "127.0.0.1" if config.pac_bind_localhost else "0.0.0.0"
    results = [
        _command("ss-local"),
        _command("gsettings"),
        _socks_port("SOCKS port", config.profile.local_port, config.socks_listen_address),
        _service_port("HTTP proxy port", config.http_port, config.http_listen_address),
        _service_port("PAC port", config.pac_port, pac_host),
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
