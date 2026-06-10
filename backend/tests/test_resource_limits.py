from __future__ import annotations

from app.services.resource_limits import MemoryAdmissionController, MemorySnapshot, estimate_image_memory_cost


MiB = 1024 * 1024


def test_memory_controller_allows_small_tasks_within_budget() -> None:
    controller = MemoryAdmissionController(
        snapshot_provider=lambda: MemorySnapshot(total=1024 * MiB, available=1024 * MiB),
        min_system_reserved=128 * MiB,
        max_budget_fraction=1.0,
    )

    first = controller.try_acquire(256 * MiB)
    assert first is not None
    second = controller.try_acquire(256 * MiB)
    assert second is not None
    third = controller.try_acquire(256 * MiB)

    assert third is not None
    first.release()
    second.release()
    third.release()


def test_memory_controller_blocks_large_tasks_until_memory_is_released() -> None:
    controller = MemoryAdmissionController(
        snapshot_provider=lambda: MemorySnapshot(total=1024 * MiB, available=900 * MiB),
        min_system_reserved=128 * MiB,
        max_budget_fraction=1.0,
    )

    large = controller.try_acquire(650 * MiB)
    assert large is not None
    blocked = controller.try_acquire(128 * MiB)
    assert blocked is None

    large.release()
    after_release = controller.try_acquire(128 * MiB)
    assert after_release is not None
    after_release.release()


def test_memory_controller_rejects_single_task_over_budget() -> None:
    controller = MemoryAdmissionController(
        snapshot_provider=lambda: MemorySnapshot(total=1024 * MiB, available=700 * MiB),
        min_system_reserved=128 * MiB,
        max_budget_fraction=1.0,
    )

    denied = controller.try_acquire(800 * MiB)

    assert denied is None


def test_estimated_image_memory_cost_scales_with_pixels() -> None:
    small = estimate_image_memory_cost(1024, 768, "RGB")
    large = estimate_image_memory_cost(8000, 6000, "RGB")

    assert small >= 16 * MiB
    assert large > small
