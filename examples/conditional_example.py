import flyte_migrate  # noqa: F401, I001
import logging

from flytekit import task, workflow


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


@task
def conditional_logic(n: float) -> float:
    """
    Simple conditional logic within a task.

    Note: flytekit.conditional() for workflow-level branching is not yet
    supported in flyte-migrate. For now, use conditionals within tasks.
    """
    if n > 0:
        return n * n
    else:
        return n * 2


@workflow
def conditional_wf(n: float = 3.0) -> float:
    """
    Demonstrates conditional logic in workflows.

    Note: flytekit.conditional() workflow branching is not yet supported.
    This example shows task-level conditionals instead.
    """
    result = conditional_logic(n=n)
    return result


# V1 conditional API example (not yet supported):
# from flytekit import conditional
#
# @workflow
# def conditional_wf_v1(n: float = 3.0) -> float:
#     result = (
#         conditional("positive_check")
#         .if_(is_positive(n=n).is_true())
#         .then(calculate_square(n=n))
#         .else_()
#         .then(calculate_double(n=n))
#     )
#     return result


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(
        conditional_wf, n=5.0
    )
    print(run.name)
    print(run.url)
