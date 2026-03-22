import flyte_migrate  # noqa: F401, I001
import logging
from datetime import timedelta

from flytekit import ImageSpec, Resources, task, workflow


# Shared image for all tasks
image = ImageSpec(packages=["pandas"])


@task(
    cache=True,
    cache_version="1.0",
    retries=2,
    timeout=timedelta(minutes=5),
    interruptible=True,
    requests=Resources(cpu="2", mem="2Gi"),
    limits=Resources(cpu="4", mem="4Gi"),
    container_image=image,
)
def classify(x: int) -> str:
    """Classify the input as positive, negative, or zero."""
    if x > 0:
        return "positive"
    elif x < 0:
        return "negative"
    return "zero"


@task(
    cache=True,
    cache_version="1.0",
    retries=2,
    timeout=timedelta(minutes=5),
    requests=Resources(cpu="2", mem="2Gi"),
    limits=Resources(cpu="4", mem="4Gi"),
    container_image=image,
)
def double(x: int) -> int:
    """Double the input value."""
    return x * 2


@task(
    retries=2,
    timeout=timedelta(minutes=5),
    interruptible=True,
    requests=Resources(cpu="2", mem="2Gi"),
    limits=Resources(cpu="4", mem="4Gi"),
    container_image=image,
)
def negate(x: int) -> int:
    """Negate the input value."""
    return -x


@task(
    retries=2,
    timeout=timedelta(minutes=5),
    requests=Resources(cpu="2", mem="2Gi"),
    limits=Resources(cpu="4", mem="4Gi"),
    container_image=image,
)
def square(x: int) -> int:
    """Square the input value."""
    return x * x


@task(
    cache=True,
    cache_version="1.0",
    requests=Resources(cpu="2", mem="2Gi"),
    limits=Resources(cpu="4", mem="4Gi"),
    container_image=image,
)
def add(a: int, b: int) -> int:
    """Add two values together."""
    return a + b


@workflow
def conditional_wf(x: int) -> int:
    """
    A workflow demonstrating conditional branching with v1 flytekit APIs.

    In v1, flytekit.conditional was used for branching. Since the shim converts
    workflows into v2 tasks (plain Python functions), we use native Python
    if/elif/else — which is the idiomatic v2 approach.

    The workflow:
    1. Classifies x as positive, negative, or zero
    2. Branches based on classification:
       - positive: double(x) then add(doubled, x)
       - negative: negate(x) then add(negated, x)
       - zero: square(x) (returns 0)
    3. Returns the final result

    Task dependencies are expressed via sequential calls (v2 equivalent of
    chain_entities / >> operator from v1).
    """
    label = classify(x=x)

    # Conditional branching — plain Python if/else replaces flytekit.conditional
    # since workflows are Python functions in v2
    if label == "positive":
        # Chain: classify -> double -> add (sequential dependency)
        doubled = double(x=x)
        result = add(a=doubled, b=x)
    elif label == "negative":
        # Chain: classify -> negate -> add (sequential dependency)
        negated = negate(x=x)
        result = add(a=negated, b=x)
    else:
        # Chain: classify -> square
        result = square(x=x)

    return result


if __name__ == "__main__":
    """
    Local execution:
        uv pip install -e .
        python examples/conditional_wf.py

    Remote execution (runs on v2 cluster):
        python examples/conditional_wf.py
    """
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(conditional_wf, x=10)
    print(run.name)
    print(run.url)
    run.wait(quiet=False)
