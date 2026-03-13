import flyte_migrate  # noqa: F401, I001
import logging
import random

from flytekit import task, workflow


@task(retries=3)
def unreliable_task(failure_rate: float) -> str:
    """
    A task that randomly fails based on the failure_rate parameter.

    Uses the retries=3 decorator parameter to automatically retry on failure.
    This demonstrates flytekit's built-in retry mechanism.
    """
    if random.random() < failure_rate:
        raise RuntimeError(
            f"Random failure (rate={failure_rate}). Flyte will auto-retry up to 3 times."
        )
    return "success"


@task(timeout=60)
def timeout_task(sleep_seconds: int) -> str:
    """
    A task with a timeout limit.

    Demonstrates the timeout parameter which limits how long a task can run.
    If the task exceeds the timeout, Flyte will terminate it.
    """
    import time

    time.sleep(min(sleep_seconds, 5))  # Cap at 5s for safety in examples
    return f"completed in {sleep_seconds}s"


@task
def validate_input(value: int) -> int:
    """
    A task that validates its input and raises a clear error.

    Demonstrates explicit error handling for invalid inputs.
    """
    if value < 0:
        raise ValueError(f"Input must be non-negative, got {value}")
    if value > 1000:
        raise ValueError(f"Input must be <= 1000, got {value}")
    return value * 2


@task
def safe_divide(numerator: float, denominator: float) -> float:
    """
    A task that handles division safely.

    Demonstrates defensive programming within tasks.
    """
    if denominator == 0:
        return float("inf")
    return numerator / denominator


@workflow
def error_handling_wf(value: int = 42, failure_rate: float = 0.3) -> str:
    """
    Demonstrates error handling and retry patterns in Flyte workflows.

    Exercises: retries, timeout, input validation, defensive programming.
    """
    validated = validate_input(value=value)
    ratio = safe_divide(numerator=float(validated), denominator=2.0)
    result = unreliable_task(failure_rate=failure_rate)
    timed = timeout_task(sleep_seconds=1)
    return result


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(
        error_handling_wf
    )
    print(run.name)
    print(run.url)
