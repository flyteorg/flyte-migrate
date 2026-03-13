import flyte_migrate  # noqa: F401, I001
import logging

from flytekit import conditional, task, workflow


@task
def calculate_square(n: float) -> float:
    """Return the square of a number."""
    return n * n


@task
def calculate_double(n: float) -> float:
    """Return double a number."""
    return n * 2


@task
def is_positive(n: float) -> bool:
    """Check if a number is positive."""
    return n > 0


@task
def negate(n: float) -> float:
    """Negate a number."""
    return -n


@workflow
def conditional_wf(n: float = 3.0) -> float:
    """
    Demonstrates conditional branching in workflows.

    If n > 0, square it. Otherwise, double it.
    Uses flytekit.conditional for branching logic.
    """
    result = (
        conditional("positive_check")
        .if_(is_positive(n=n).is_true())
        .then(calculate_square(n=n))
        .else_()
        .then(calculate_double(n=n))
    )
    return result


@workflow
def multi_branch_wf(n: float = 5.0) -> float:
    """
    Demonstrates multi-branch conditional logic.

    If n > 0, square it. If n == 0, return 0. Otherwise, negate and double.
    """
    pos = is_positive(n=n)
    result = (
        conditional("multi_check")
        .if_(pos.is_true())
        .then(calculate_square(n=n))
        .else_()
        .then(calculate_double(n=negate(n=n)))
    )
    return result


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(
        conditional_wf, n=5.0
    )
    print(run.name)
    print(run.url)
