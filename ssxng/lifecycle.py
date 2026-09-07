from __future__ import annotations

import os
import signal
import time
from pathlib import Path

from .config import RUNTIME_FILE


def _read_cmdline(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (OSError, ValueError):
        return []
    return [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]


def _read_status_value(pid: int, key: str) -> str | None:
    try:
        lines = Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    prefix = key + ":"
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def _same_uid(pid: int) -> bool:
    value = _read_status_value(pid, "Uid")
    if not value:
        return False
    try:
        real_uid = int(value.split()[0])
    except (ValueError, IndexError):
        return False
    return real_uid == os.getuid()


def _ppid(pid: int) -> int | None:
    value = _read_status_value(pid, "PPid")
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def is_managed_orphan_ss_local(pid: int) -> bool:
    """Return True only for an orphaned ss-local started with our runtime file.

    Requiring the same uid, PPID 1, ss-local executable name, and the exact
    LibreWing runtime path avoids touching unrelated user proxies.
    """
    if pid <= 1 or not _same_uid(pid) or _ppid(pid) != 1:
        return False
    argv = _read_cmdline(pid)
    if not argv:
        return False
    executable = Path(argv[0]).name
    if executable != "ss-local":
        return False
    runtime = str(RUNTIME_FILE)
    return any(argv[i] == "-c" and argv[i + 1] == runtime for i in range(len(argv) - 1))


def find_managed_orphan_ss_local() -> list[int]:
    proc = Path("/proc")
    if not proc.exists():
        return []
    result: list[int] = []
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if is_managed_orphan_ss_local(pid):
            result.append(pid)
    return result


def cleanup_managed_orphan_ss_local(timeout: float = 1.5) -> list[int]:
    """Terminate stale ss-local children left after an abnormal GUI exit."""
    pids = find_managed_orphan_ss_local()
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            continue

    # Always re-check once after SIGTERM, even when timeout=0. This prevents a
    # needless SIGKILL when the process has already disappeared immediately.
    remaining = {pid for pid in pids if Path(f"/proc/{pid}").exists()}
    deadline = time.monotonic() + max(0.0, timeout)
    while remaining and time.monotonic() < deadline:
        time.sleep(0.05)
        remaining = {pid for pid in remaining if Path(f"/proc/{pid}").exists()}

    for pid in remaining:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    return pids
