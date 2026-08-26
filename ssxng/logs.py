from __future__ import annotations

from collections import deque
from pathlib import Path

from .config import LOG_FILE


def tail_log(lines: int = 200, path: Path | None = None) -> str:
    target = path or LOG_FILE
    if lines <= 0 or not target.exists():
        return ""
    try:
        with target.open("r", encoding="utf-8", errors="replace") as handle:
            return "".join(deque(handle, maxlen=lines))
    except OSError:
        return ""


def clear_log(path: Path | None = None) -> None:
    target = path or LOG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("", encoding="utf-8")
