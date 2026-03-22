"""
Edge case examples for flyte-migrate shim:

- Task with no inputs, no outputs (side-effect only)
- Task with very long timeout
- Task with 0 retries (default)
- Workflow with single task (simplest case)
- Workflow with many tasks (10+)
- Task that raises an exception
"""

import flyte_migrate  # noqa: F401, I001
import logging
from datetime import timedelta

from flytekit import ImageSpec, task, workflow

image = ImageSpec(packages=["setuptools"])


# ---------------------------------------------------------------------------
# Side-effect only task (no inputs, no outputs)
# ---------------------------------------------------------------------------


@task(container_image=image)
def side_effect_task() -> None:
    """Task with no inputs and no outputs — pure side effect."""
    print("Side effect executed!")


# ---------------------------------------------------------------------------
# Very long timeout
# ---------------------------------------------------------------------------


@task(container_image=image, timeout=timedelta(hours=24))
def long_timeout_task(x: int) -> int:
    """Task with a 24-hour timeout."""
    return x


# ---------------------------------------------------------------------------
# Zero retries (explicit default)
# ---------------------------------------------------------------------------


@task(container_image=image, retries=0)
def no_retry_task(x: int) -> int:
    """Task with explicitly zero retries."""
    return x * 2


# ---------------------------------------------------------------------------
# Many tasks for scalability test
# ---------------------------------------------------------------------------


@task(container_image=image)
def step_0(x: int) -> int:
    return x + 0


@task(container_image=image)
def step_1(x: int) -> int:
    return x + 1


@task(container_image=image)
def step_2(x: int) -> int:
    return x + 2


@task(container_image=image)
def step_3(x: int) -> int:
    return x + 3


@task(container_image=image)
def step_4(x: int) -> int:
    return x + 4


@task(container_image=image)
def step_5(x: int) -> int:
    return x + 5


@task(container_image=image)
def step_6(x: int) -> int:
    return x + 6


@task(container_image=image)
def step_7(x: int) -> int:
    return x + 7


@task(container_image=image)
def step_8(x: int) -> int:
    return x + 8


@task(container_image=image)
def step_9(x: int) -> int:
    return x + 9


@task(container_image=image)
def step_10(x: int) -> int:
    return x + 10


# ---------------------------------------------------------------------------
# Task that raises an exception
# ---------------------------------------------------------------------------


@task(container_image=image)
def error_task(x: int) -> int:
    """Task that always raises an exception for testing error handling."""
    raise ValueError(f"Intentional error with x={x}")


# ---------------------------------------------------------------------------
# Simplest workflow (single task)
# ---------------------------------------------------------------------------


@workflow
def single_task_wf(x: int = 1) -> int:
    """Simplest possible workflow: one task."""
    return no_retry_task(x=x)


# ---------------------------------------------------------------------------
# Many-task workflow (10+ tasks chained)
# ---------------------------------------------------------------------------


@workflow
def many_tasks_wf(x: int = 0) -> int:
    """Workflow with 11 chained tasks to test scalability."""
    a = step_0(x=x)
    b = step_1(x=a)
    c = step_2(x=b)
    d = step_3(x=c)
    e = step_4(x=d)
    f = step_5(x=e)
    g = step_6(x=f)
    h = step_7(x=g)
    i = step_8(x=h)
    j = step_9(x=i)
    return step_10(x=j)


# ---------------------------------------------------------------------------
# Side-effect workflow
# ---------------------------------------------------------------------------


@workflow
def side_effect_wf() -> None:
    """Workflow with side-effect only task."""
    side_effect_task()


# ---------------------------------------------------------------------------
# Long timeout workflow
# ---------------------------------------------------------------------------


@workflow
def long_timeout_wf(x: int = 42) -> int:
    """Workflow using task with long timeout."""
    return long_timeout_task(x=x)


# ---------------------------------------------------------------------------
# Error workflow
# ---------------------------------------------------------------------------


@workflow
def error_wf(x: int = 1) -> int:
    """Workflow that will fail due to error_task raising ValueError."""
    return error_task(x=x)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)

    # Run the many-tasks workflow
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(many_tasks_wf, x=0)
    print(f"many_tasks_wf: {run.name}")
    print(f"many_tasks_wf: {run.url}")

    # Run the single-task workflow
    run2 = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(single_task_wf, x=5)
    print(f"single_task_wf: {run2.name}")
    print(f"single_task_wf: {run2.url}")

    # Run the side-effect workflow
    run3 = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(side_effect_wf)
    print(f"side_effect_wf: {run3.name}")
    print(f"side_effect_wf: {run3.url}")

    # Run the long timeout workflow
    run4 = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(long_timeout_wf, x=42)
    print(f"long_timeout_wf: {run4.name}")
    print(f"long_timeout_wf: {run4.url}")

    # Run the error workflow (expected to fail)
    run5 = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(error_wf, x=99)
    print(f"error_wf: {run5.name}")
    print(f"error_wf: {run5.url}")
