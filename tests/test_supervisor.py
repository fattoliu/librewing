from ssxng.config import AppConfig
from ssxng.supervisor import RuntimeSupervisor


class FakeService:
    def __init__(self, running=True, restart_error=None):
        self.is_running = running
        self.restart_error = restart_error
        self.restarts = 0
        self.stops = 0

    def running(self):
        return self.is_running

    def stop(self):
        self.stops += 1
        self.is_running = False

    def restart(self):
        self.restarts += 1
        if self.restart_error:
            raise RuntimeError(self.restart_error)
        self.is_running = True


def make_supervisor(*, mode="pac", core=True, http=True, pac=True, pac_error=None):
    config = AppConfig(mode=mode)
    services = {
        "core": FakeService(core),
        "http": FakeService(http),
        "pac": FakeService(pac, pac_error),
    }
    events = []
    fail_closed = []
    supervisor = RuntimeSupervisor(
        config,
        services["core"],
        services["http"],
        services["pac"],
        fail_closed=lambda: fail_closed.append(True),
        emit=events.append,
    )
    return supervisor, services, events, fail_closed


def test_healthy_snapshot_is_structured_and_quiet():
    supervisor, _services, events, fail_closed = make_supervisor()

    snapshot = supervisor.tick()

    assert snapshot.healthy is True
    assert snapshot.mode == "pac"
    assert snapshot.core_expected is True
    assert snapshot.http_expected is True
    assert snapshot.pac_expected is True
    assert events == []
    assert fail_closed == []


def test_core_failure_fails_closed_once_and_stops_http():
    supervisor, services, events, fail_closed = make_supervisor(core=False)

    first = supervisor.tick()
    second = supervisor.tick()

    assert first.healthy is False
    assert second.healthy is False
    assert services["http"].stops == 2
    assert fail_closed == [True]
    assert [(event.component, event.state) for event in events] == [("core", "failed")]


def test_http_bridge_is_restarted_automatically():
    supervisor, services, events, fail_closed = make_supervisor(http=False)

    snapshot = supervisor.tick()

    assert snapshot.healthy is True
    assert services["http"].restarts == 1
    assert [(event.component, event.state) for event in events] == [("http", "restarted")]
    assert fail_closed == []


def test_pac_failure_in_auto_mode_fails_closed_without_alert_loop():
    supervisor, services, events, fail_closed = make_supervisor(
        pac=False, pac_error="address in use"
    )

    supervisor.tick()
    supervisor.tick()

    assert services["pac"].restarts == 2
    assert fail_closed == [True]
    assert [(event.component, event.state) for event in events] == [("pac", "failed")]
    assert events[0].detail == "address in use"


def test_pac_service_recovers_automatically():
    supervisor, services, events, _fail_closed = make_supervisor(
        pac=False, pac_error="temporary failure"
    )
    supervisor.tick()
    services["pac"].restart_error = None

    snapshot = supervisor.tick()

    assert snapshot.healthy is True
    assert [(event.component, event.state) for event in events] == [
        ("pac", "failed"),
        ("pac", "restarted"),
    ]
