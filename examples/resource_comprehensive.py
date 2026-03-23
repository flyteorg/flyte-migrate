import flyte_migrate  # noqa: F401, I001

from flytekit import ImageSpec, Resources, task, workflow

image = ImageSpec(packages=["pandas"])


# --- requests-only (cpu, mem) ---
@task(
    container_image=image,
    requests=Resources(cpu="1", mem="512Mi"),
)
def task_requests_only(x: int) -> str:
    return f"requests_only: x={x}"


# --- limits-only (cpu, mem) ---
@task(
    container_image=image,
    limits=Resources(cpu="2", mem="1Gi"),
)
def task_limits_only(x: int) -> str:
    return f"limits_only: x={x}"


# --- both requests AND limits ---
@task(
    container_image=image,
    requests=Resources(cpu="1", mem="512Mi"),
    limits=Resources(cpu="2", mem="1Gi"),
)
def task_requests_and_limits(x: int) -> str:
    return f"requests_and_limits: x={x}"


# --- resources param alone ---
@task(
    container_image=image,
    resources=Resources(cpu="1", mem="1Gi"),
)
def task_resources_param(x: int) -> str:
    return f"resources_param: x={x}"


# --- shared_memory=True ---
@task(
    container_image=image,
    requests=Resources(cpu="1", mem="512Mi"),
    shared_memory=True,
)
def task_shared_memory_true(x: int) -> str:
    return f"shared_memory_true: x={x}"


# --- shared_memory="2Gi" ---
@task(
    container_image=image,
    requests=Resources(cpu="1", mem="512Mi"),
    shared_memory="2Gi",
)
def task_shared_memory_explicit(x: int) -> str:
    return f"shared_memory_2Gi: x={x}"


# --- ephemeral_storage in requests ---
@task(
    container_image=image,
    requests=Resources(cpu="1", mem="512Mi", ephemeral_storage="5Gi"),
)
def task_ephemeral_storage(x: int) -> str:
    return f"ephemeral_storage: x={x}"


# --- GPU count-only ---
# NOTE: v2 flyte.Resources validates GPU against a known set of accelerator literals
# (e.g., "T4:1", "A100:2"). The v1 pattern of gpu="1" (count-only without a named
# accelerator) is NOT supported in v2. This is a compatibility gap in the shim —
# _format_gpu produces "1" which v2 rejects at definition time.
# To use GPUs in v2, you must specify a named accelerator via the `accelerator` param.
# Example: @task(requests=Resources(cpu="1", mem="1Gi"), accelerator=T4)


@workflow
def resource_comprehensive_wf(x: int = 42) -> list[str]:
    a = task_requests_only(x=x)
    b = task_limits_only(x=x)
    c = task_requests_and_limits(x=x)
    d = task_resources_param(x=x)
    e = task_shared_memory_true(x=x)
    f = task_shared_memory_explicit(x=x)
    g = task_ephemeral_storage(x=x)
    return [a, b, c, d, e, f, g]


if __name__ == "__main__":
    import logging

    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(resource_comprehensive_wf, x=42)
    print(run.name)
    print(run.url)
