import signal

from ssxng import lifecycle


def test_managed_process_requires_same_user_and_exact_runtime(monkeypatch):
    monkeypatch.setattr(lifecycle, "_same_uid", lambda pid: True)
    monkeypatch.setattr(
        lifecycle,
        "_read_cmdline",
        lambda pid: ["/usr/bin/ss-local", "-c", str(lifecycle.RUNTIME_FILE), "-v"],
    )
    assert lifecycle.is_managed_ss_local(1234)


def test_unrelated_ss_local_is_never_reclaimed(monkeypatch):
    monkeypatch.setattr(lifecycle, "_same_uid", lambda pid: True)
    monkeypatch.setattr(
        lifecycle,
        "_read_cmdline",
        lambda pid: ["/usr/bin/ss-local", "-c", "/etc/shadowsocks-libev/config.json", "-v"],
    )
    assert not lifecycle.is_managed_ss_local(1234)


def test_cleanup_sends_sigterm_and_returns_reclaimed_pids(monkeypatch):
    monkeypatch.setattr(lifecycle, "find_managed_ss_local", lambda: [1234])
    sent = []
    monkeypatch.setattr(lifecycle.os, "kill", lambda pid, sig: sent.append((pid, sig)))

    class MissingProc:
        def exists(self):
            return False

    monkeypatch.setattr(lifecycle, "Path", lambda value: MissingProc())

    assert lifecycle.cleanup_managed_ss_local(timeout=0) == [1234]
    assert sent == [(1234, signal.SIGTERM)]


def test_cleanup_escalates_to_sigkill_when_process_survives(monkeypatch):
    monkeypatch.setattr(lifecycle, "find_managed_ss_local", lambda: [4321])
    sent = []
    monkeypatch.setattr(lifecycle.os, "kill", lambda pid, sig: sent.append((pid, sig)))

    class ExistingProc:
        def exists(self):
            return True

    monkeypatch.setattr(lifecycle, "Path", lambda value: ExistingProc())

    assert lifecycle.cleanup_managed_ss_local(timeout=0) == [4321]
    assert sent == [(4321, signal.SIGTERM), (4321, signal.SIGKILL)]
