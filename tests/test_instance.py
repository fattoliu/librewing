import pytest

from ssxng.instance import AlreadyRunningError, InstanceLock


def test_instance_lock_blocks_second_holder(tmp_path):
    path = tmp_path / "app.lock"
    first = InstanceLock(path).acquire()
    try:
        with pytest.raises(AlreadyRunningError):
            InstanceLock(path).acquire()
    finally:
        first.release()


def test_instance_lock_can_be_reacquired_after_release(tmp_path):
    path = tmp_path / "app.lock"
    first = InstanceLock(path).acquire()
    first.release()
    second = InstanceLock(path).acquire()
    second.release()
