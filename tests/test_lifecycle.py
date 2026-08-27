from ssxng import lifecycle


def test_managed_orphan_requires_same_user_ppid1_and_exact_runtime(monkeypatch):
    monkeypatch.setattr(lifecycle, "_same_uid", lambda pid: True)
    monkeypatch.setattr(lifecycle, "_ppid", lambda pid: 1)
    monkeypatch.setattr(
        lifecycle,
        "_read_cmdline",
        lambda pid: ["/usr/bin/ss-local", "-c", str(lifecycle.RUNTIME_FILE), "-v"],
    )
    assert lifecycle.is_managed_orphan_ss_local(1234)


def test_unrelated_ss_local_is_never_reclaimed(monkeypatch):
    monkeypatch.setattr(lifecycle, "_same_uid", lambda pid: True)
    monkeypatch.setattr(lifecycle, "_ppid", lambda pid: 1)
    monkeypatch.setattr(
        lifecycle,
        "_read_cmdline",
        lambda pid: ["/usr/bin/ss-local", "-c", "/etc/shadowsocks-libev/config.json", "-v"],
    )
    assert not lifecycle.is_managed_orphan_ss_local(1234)


def test_non_orphan_managed_process_is_not_reclaimed(monkeypatch):
    monkeypatch.setattr(lifecycle, "_same_uid", lambda pid: True)
    monkeypatch.setattr(lifecycle, "_ppid", lambda pid: 987)
    monkeypatch.setattr(
        lifecycle,
        "_read_cmdline",
        lambda pid: ["/usr/bin/ss-local", "-c", str(lifecycle.RUNTIME_FILE), "-v"],
    )
    assert not lifecycle.is_managed_orphan_ss_local(1234)
