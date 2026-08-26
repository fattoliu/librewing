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
