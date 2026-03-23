import flyte_migrate  # noqa: F401, I001
import logging
import os
from datetime import timedelta

from flytekit import Documentation, ImageSpec, Resources, task, workflow

image = ImageSpec(packages=["pandas"])

# ---------------------------------------------------------------------------
# 1. cache + cache_version
# ---------------------------------------------------------------------------


@task(cache=True, cache_version="2.0", container_image=image)
def cached_task(x: int) -> int:
    """Task with caching enabled and a cache_version (v2 ignores cache_version)."""
    return x * 2


# ---------------------------------------------------------------------------
# 2. retries + timeout + interruptible
# ---------------------------------------------------------------------------


@task(retries=3, timeout=timedelta(minutes=10), interruptible=True, container_image=image)
def retry_timeout_task(x: int) -> int:
    """Task with retries, timeout, and interruptible flags."""
    return x + 1


# ---------------------------------------------------------------------------
# 3. docs (Documentation)
# ---------------------------------------------------------------------------


@task(docs=Documentation(short_description="Adds 10 to the input value"), container_image=image)
def documented_task(x: int) -> int:
    """Task with a Documentation object."""
    return x + 10


# ---------------------------------------------------------------------------
# 4. environment dict
# ---------------------------------------------------------------------------


@task(environment={"MY_VAR": "hello", "ANOTHER_VAR": "world"}, container_image=image)
def env_var_task(x: int) -> str:
    """Task that reads environment variables injected via the environment param."""
    val = os.getenv("MY_VAR", "NOT_SET")
    return f"MY_VAR={val}, x={x}"


# ---------------------------------------------------------------------------
# 5. enable_deck
# ---------------------------------------------------------------------------


@task(enable_deck=True, container_image=image)
def deck_task(x: int) -> int:
    """Task with enable_deck=True which maps to report=True in v2."""
    import flytekit

    flytekit.Deck("Results", f"<p>The value of x is {x}</p>")
    return x


# ---------------------------------------------------------------------------
# 6. requests + limits (separate Resources)
# ---------------------------------------------------------------------------


@task(
    requests=Resources(cpu="1", mem="1Gi"),
    limits=Resources(cpu="2", mem="2Gi"),
    container_image=image,
)
def resource_req_limit_task(x: int) -> int:
    """Task with separate requests and limits."""
    return x * 3


# ---------------------------------------------------------------------------
# 7. combined resources param
# ---------------------------------------------------------------------------


@task(resources=Resources(cpu="1", mem="512Mi"), container_image=image)
def resource_combined_task(x: int) -> int:
    """Task with a single combined resources param."""
    return x * 4


# ---------------------------------------------------------------------------
# 8. Unknown kwargs — should be logged but not raise
# ---------------------------------------------------------------------------


@task(
    container_image=image,
    execution_mode=1,  # type: ignore[call-arg]
    node_dependency_hints=[],  # type: ignore[call-arg]
    pickle_untyped=True,  # type: ignore[call-arg]
)
def unknown_kwargs_task(x: int) -> int:
    """Task with unknown kwargs that should be silently ignored."""
    return x


# ---------------------------------------------------------------------------
# Workflow calling all tasks
# ---------------------------------------------------------------------------


@workflow
def all_task_params_wf(x: int = 5) -> str:
    a = cached_task(x=x)
    b = retry_timeout_task(x=a)
    c = documented_task(x=b)
    d = env_var_task(x=c)
    e = deck_task(x=c)
    f = resource_req_limit_task(x=e)
    g = resource_combined_task(x=f)
    unknown_kwargs_task(x=g)
    return d


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(all_task_params_wf, x=5)
    print(run.name)
    print(run.url)
