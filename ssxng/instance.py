from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import TextIO

from .config import APP_DIR, ensure_private_directory

LOCK_FILE = APP_DIR / "app.lock"


class AlreadyRunningError(RuntimeError):
    pass


class InstanceLock:
    """Advisory process lock preventing two tray clients owning the same ports."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path or LOCK_FILE)
        self.handle: TextIO | None = None

    def acquire(self) -> "InstanceLock":
        ensure_private_directory(self.path.parent)
        descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_RDWR, 0o600)
        os.fchmod(descriptor, 0o600)
        handle = os.fdopen(descriptor, "a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise AlreadyRunningError("ShadowsocksX-NG Linux is already running") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        self.handle = handle
        return self

    def release(self) -> None:
        if self.handle is None:
            return
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None

    def __enter__(self) -> "InstanceLock":
        return self.acquire()

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()
