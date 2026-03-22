import flyte_migrate  # noqa: F401, I001
import functools
import logging
from typing import List

from flytekit import Resources, map_task, task, workflow


# --------------------------------------------------------------------------- #
# 1. Basic map_task — simple int -> str mapping
# --------------------------------------------------------------------------- #
@task
def square(x: int) -> int:
    return x * x


# --------------------------------------------------------------------------- #
# 2. map_task with partial — bind some arguments via functools.partial
# --------------------------------------------------------------------------- #
@task
def multiply(x: int, factor: int) -> int:
    return x * factor


# --------------------------------------------------------------------------- #
# 3. map_task with typed collections — List[int] input, List[str] output
# --------------------------------------------------------------------------- #
@task
def int_to_label(val: int) -> str:
    return f"item-{val}"


# --------------------------------------------------------------------------- #
# 4. Nested: map_task calling a task with resources
# --------------------------------------------------------------------------- #
@task(requests=Resources(cpu="1", mem="512Mi"))
def heavy_compute(n: int) -> float:
    """Simulate a resource-intensive computation."""
    total = 0.0
    for i in range(1, n + 1):
        total += 1.0 / i
    return round(total, 4)


# --------------------------------------------------------------------------- #
# Workflow that ties everything together
# --------------------------------------------------------------------------- #
@workflow
def map_task_advanced_wf(
    data: List[int] = [1, 2, 3, 4, 5],
    factor: int = 10,
) -> List[float]:
    # 1. Basic map_task
    squared: List[int] = map_task(square)(data)

    # 2. map_task with partial
    partial_multiply = functools.partial(multiply, factor=factor)
    scaled: List[int] = map_task(partial_multiply)(squared)

    # 3. map_task with typed collections (int -> str)
    _labels: List[str] = map_task(int_to_label)(scaled)

    # 4. map_task with resource-annotated task (results flow from previous)
    results: List[float] = map_task(heavy_compute)(scaled)

    return results


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(map_task_advanced_wf, data=[1, 2, 3, 4, 5])
    print(run.name)
    print(run.url)
    run.wait(quiet=False)
