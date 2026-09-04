import stat

import ssxng.core as core
from ssxng.logs import clear_log, tail_log


def test_tail_log_returns_last_lines(tmp_path):
    path = tmp_path / "app.log"
    path.write_text("one\ntwo\nthree\n", encoding="utf-8")
    assert tail_log(2, path) == "two\nthree\n"


def test_clear_log(tmp_path):
    path = tmp_path / "nested" / "app.log"
    path.parent.mkdir(parents=True)
    path.write_text("hello", encoding="utf-8")
    clear_log(path)
    assert path.read_text(encoding="utf-8") == ""
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_proxy_log_is_private(tmp_path, monkeypatch):
    path = tmp_path / "state" / "app.log"
    monkeypatch.setattr(core, "LOG_FILE", path)

    handle = core._open_log("test")
    handle.close()

    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
