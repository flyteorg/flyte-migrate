import flyte_migrate  # noqa: F401, I001
import functools
import logging
from typing import List

from flytekit import ImageSpec, dynamic, map_task, task, workflow


image = ImageSpec(packages=["setuptools"])


# ---------------------------------------------------------------------------
# Tasks for map_task testing
# ---------------------------------------------------------------------------


@task(container_image=image)
def square(x: int) -> int:
    return x * x


@task(container_image=image)
def multiply(x: int, factor: int) -> int:
    return x * factor


@task(container_image=image)
def add_offset(x: int, offset: int) -> int:
    return x + offset


# ---------------------------------------------------------------------------
# Tasks for dynamic / subworkflow testing
# ---------------------------------------------------------------------------


@task(container_image=image)
def increment(x: int) -> int:
    return x + 1


@task(container_image=image)
def sum_list(values: List[int]) -> int:
    return sum(values)


@task(container_image=image)
def format_result(label: str, value: int) -> str:
    return f"{label}: {value}"


# ---------------------------------------------------------------------------
# Subworkflow: called from within the main workflow
# ---------------------------------------------------------------------------


@workflow
def sub_workflow(values: List[int], label: str) -> str:
    total = sum_list(values=values)
    return format_result(label=label, value=total)


# ---------------------------------------------------------------------------
# Dynamic: spawns variable number of tasks based on input
# ---------------------------------------------------------------------------


@dynamic(container_image=image)
def dynamic_increment(n: int) -> List[int]:
    """Spawn n increment tasks."""
    results: List[int] = []
    for i in range(n):
        results.append(increment(x=i))
    return results


# ---------------------------------------------------------------------------
# Nested dynamic: dynamic spawning another dynamic
# ---------------------------------------------------------------------------


@dynamic(container_image=image)
def inner_dynamic(start: int, count: int) -> List[int]:
    results: List[int] = []
    for i in range(count):
        results.append(increment(x=start + i))
    return results


@dynamic(container_image=image)
def outer_dynamic(groups: int, per_group: int) -> List[int]:
    """Dynamic that spawns inner_dynamic for each group, then sums results."""
    all_totals: List[int] = []
    for g in range(groups):
        group_results = inner_dynamic(start=g * per_group, count=per_group)
        total = sum_list(values=group_results)
        all_totals.append(total)
    return all_totals


# ---------------------------------------------------------------------------
# Main workflow exercising all control flow patterns
# ---------------------------------------------------------------------------


@workflow
def control_flow_wf(
    data: List[int] = [1, 2, 3, 4, 5],
    factor: int = 10,
    n_dynamic: int = 4,
) -> str:
    # 1. Basic map_task
    squared: List[int] = map_task(square)(data)

    # 2. map_task with functools.partial
    partial_mul = functools.partial(multiply, factor=factor)
    scaled: List[int] = map_task(partial_mul)(squared)

    # 3. map_task with concurrency (forwarded to flyte.map)
    partial_offset = functools.partial(add_offset, offset=1)
    _with_concurrency: List[int] = map_task(partial_offset, concurrency=2)(scaled)

    # 4. map_task with min_success_ratio (accepted, not forwarded — v2 limitation)
    _with_ratio: List[int] = map_task(square, min_success_ratio=0.75)(data)

    # 5. @dynamic: variable number of subtasks
    dynamic_results: List[int] = dynamic_increment(n=n_dynamic)

    # 6. Subworkflow: workflow calling another workflow
    sub_result: str = sub_workflow(values=dynamic_results, label="dynamic_total")

    # 7. Nested dynamic
    nested_totals: List[int] = outer_dynamic(groups=2, per_group=3)
    nested_label: str = sub_workflow(values=nested_totals, label="nested_total")

    # Combine results for final output
    _ = sub_result
    return nested_label


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(
        control_flow_wf,
        data=[1, 2, 3, 4, 5],
        factor=10,
        n_dynamic=4,
    )
    print(run.name)
    print(run.url)
    run.wait(quiet=False)
