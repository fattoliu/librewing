from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from .config import AppConfig


class Service(Protocol):
    def running(self) -> bool: ...

    def stop(self) -> None: ...


class RestartableService(Service, Protocol):
    def restart(self) -> None: ...


@dataclass(frozen=True)
class RuntimeSnapshot:
    mode: str
    core_expected: bool
    core_running: bool
    http_expected: bool
    http_running: bool
    pac_expected: bool
    pac_running: bool

    @property
    def healthy(self) -> bool:
        return all(
            (
                not self.core_expected or self.core_running,
                not self.http_expected or self.http_running,
                not self.pac_expected or self.pac_running,
            )
        )


@dataclass(frozen=True)
class RuntimeEvent:
    component: str
    state: str
    detail: str


class RuntimeSupervisor:
    """Observe, recover, and report the client runtime without UI dependencies."""

    def __init__(
        self,
        config: AppConfig,
        core: Service,
        http: RestartableService,
        pac: RestartableService,
        *,
        fail_closed: Callable[[], None],
        emit: Callable[[RuntimeEvent], None],
    ) -> None:
        self.config = config
        self.core = core
        self.http = http
        self.pac = pac
        self.fail_closed = fail_closed
        self.emit = emit
        self._failed: set[str] = set()

    def snapshot(self) -> RuntimeSnapshot:
        core_running = self.core.running()
        return RuntimeSnapshot(
            mode=self.config.mode,
            core_expected=self.config.mode != "off",
            core_running=core_running,
            http_expected=core_running and self.config.http_enabled,
            http_running=self.http.running(),
            pac_expected=True,
            pac_running=self.pac.running(),
        )

    def _recover(self, name: str, service: RestartableService) -> tuple[str | None, bool]:
        try:
            service.restart()
        except Exception as exc:
            return str(exc), False
        if service.running():
            return None, True
        return f"{name} service did not remain running after restart", False

    def tick(self) -> RuntimeSnapshot:
        before = self.snapshot()
        recovery_errors: dict[str, str] = {}
        restarted: set[str] = set()

        if not before.pac_running:
            error, recovered = self._recover("pac", self.pac)
            if error:
                recovery_errors["pac"] = error
            if recovered:
                restarted.add("pac")

        if before.core_expected and not before.core_running:
            self.http.stop()

        current = self.snapshot()
        if current.http_expected and not current.http_running:
            error, recovered = self._recover("http", self.http)
            if error:
                recovery_errors["http"] = error
            if recovered:
                restarted.add("http")

        final = self.snapshot()
        failed = {
            name
            for name, expected, running in (
                ("core", final.core_expected, final.core_running),
                ("http", final.http_expected, final.http_running),
                ("pac", final.pac_expected, final.pac_running),
            )
            if expected and not running
        }

        newly_failed = failed - self._failed
        if "core" in newly_failed or (
            "pac" in newly_failed and self.config.mode in ("pac", "global")
        ):
            self.fail_closed()
        for component in sorted(newly_failed):
            detail = recovery_errors.get(component, f"{component} service stopped unexpectedly")
            self.emit(RuntimeEvent(component, "failed", detail))
        for component in sorted(restarted):
            self.emit(RuntimeEvent(component, "restarted", f"{component} service restarted"))
        for component in sorted((self._failed - failed) - restarted):
            self.emit(RuntimeEvent(component, "recovered", f"{component} service recovered"))
        self._failed = failed
        return final
