from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import psutil


MiB = 1024 * 1024
GiB = 1024 * MiB
DEFAULT_MIN_SYSTEM_RESERVED = GiB
DEFAULT_MAX_BUDGET_FRACTION = 0.60
MIN_IMAGE_TASK_COST = 16 * MiB
VIDEO_PLACEHOLDER_COST = 16 * MiB
THUMBNAIL_MEMORY_MULTIPLIER = 3.0


@dataclass(frozen=True)
class MemorySnapshot:
    total: int
    available: int


@dataclass(frozen=True)
class MemoryStatus:
    guard_enabled: bool
    total_bytes: int | None
    available_bytes: int | None
    thumbnail_budget_bytes: int | None


class MemoryReservation:
    def __init__(self, controller: MemoryAdmissionController, cost_bytes: int) -> None:
        self._controller = controller
        self._cost_bytes = cost_bytes
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._controller.release(self._cost_bytes)

    def __enter__(self) -> MemoryReservation:
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()


SnapshotProvider = Callable[[], MemorySnapshot]


def psutil_memory_snapshot() -> MemorySnapshot:
    memory = psutil.virtual_memory()
    return MemorySnapshot(total=int(memory.total), available=int(memory.available))


def current_memory_budget(
    snapshot: MemorySnapshot | None = None,
    *,
    min_system_reserved: int = DEFAULT_MIN_SYSTEM_RESERVED,
    max_budget_fraction: float = DEFAULT_MAX_BUDGET_FRACTION,
) -> int:
    if snapshot is None:
        snapshot = psutil_memory_snapshot()
    reserved = max(min_system_reserved, int(snapshot.total * 0.20))
    available_budget = max(0, snapshot.available - reserved)
    total_cap = max(0, int(snapshot.total * max_budget_fraction))
    return min(available_budget, total_cap)


def current_memory_status() -> MemoryStatus:
    snapshot = psutil_memory_snapshot()
    return MemoryStatus(
        guard_enabled=True,
        total_bytes=snapshot.total,
        available_bytes=snapshot.available,
        thumbnail_budget_bytes=current_memory_budget(snapshot),
    )


def estimate_image_memory_cost(width: int, height: int, mode: str | None = None) -> int:
    channels = 4 if mode in {"RGBA", "CMYK", "P"} else 3
    decoded_bytes = max(0, int(width)) * max(0, int(height)) * channels
    estimated = int(decoded_bytes * THUMBNAIL_MEMORY_MULTIPLIER)
    return max(MIN_IMAGE_TASK_COST, estimated)


class MemoryAdmissionController:
    def __init__(
        self,
        snapshot_provider: SnapshotProvider = psutil_memory_snapshot,
        *,
        min_system_reserved: int = DEFAULT_MIN_SYSTEM_RESERVED,
        max_budget_fraction: float = DEFAULT_MAX_BUDGET_FRACTION,
    ) -> None:
        self._snapshot_provider = snapshot_provider
        self._min_system_reserved = min_system_reserved
        self._max_budget_fraction = max_budget_fraction
        self._reserved_bytes = 0
        self._condition = threading.Condition()

    def try_acquire(self, cost_bytes: int) -> MemoryReservation | None:
        cost = max(0, int(cost_bytes))
        with self._condition:
            return self._try_acquire_locked(cost)

    def acquire(
        self,
        cost_bytes: int,
        *,
        timeout: float = 30.0,
        poll_interval: float = 0.25,
    ) -> MemoryReservation | None:
        cost = max(0, int(cost_bytes))
        deadline = time.monotonic() + timeout
        with self._condition:
            while True:
                reservation = self._try_acquire_locked(cost)
                if reservation is not None:
                    return reservation
                if cost > self.current_budget:
                    return None
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(min(poll_interval, remaining))

    def release(self, cost_bytes: int) -> None:
        with self._condition:
            self._reserved_bytes = max(0, self._reserved_bytes - max(0, int(cost_bytes)))
            self._condition.notify_all()

    @property
    def current_budget(self) -> int:
        return current_memory_budget(
            self._snapshot_provider(),
            min_system_reserved=self._min_system_reserved,
            max_budget_fraction=self._max_budget_fraction,
        )

    def _try_acquire_locked(self, cost: int) -> MemoryReservation | None:
        budget = self.current_budget
        if cost > budget:
            return None
        if self._reserved_bytes + cost > budget:
            return None
        self._reserved_bytes += cost
        return MemoryReservation(self, cost)


default_memory_controller = MemoryAdmissionController()
