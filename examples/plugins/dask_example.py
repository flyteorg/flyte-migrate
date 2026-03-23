import flyte_migrate  # noqa: F401, I001
import logging

from flytekit import ImageSpec, Resources, task, workflow
from flytekitplugins.dask import Dask, Scheduler, WorkerGroup

custom_image = ImageSpec(python_version="3.10", packages=["flytekitplugins-dask", "numpy"])

if custom_image.is_container():
    from dask import array as da


@task(
    task_config=Dask(
        workers=WorkerGroup(
            number_of_workers=10,
            limits=Resources(cpu="4", mem="10Gi"),
        ),
    ),
    limits=Resources(cpu="1", mem="2Gi"),
    container_image=custom_image,
)
def hello_dask(size: int) -> float:
    """Basic Dask task with worker group configuration."""
    array = da.random.random(size)
    return float(array.mean().compute())


@task(
    task_config=Dask(
        workers=WorkerGroup(
            number_of_workers=5,
            image="ghcr.io/dask/dask:2024.1.0-py3.10",
            requests=Resources(cpu="2", mem="4Gi"),
            limits=Resources(cpu="4", mem="8Gi"),
        ),
        scheduler=Scheduler(
            image="ghcr.io/dask/dask:2024.1.0-py3.10",
            requests=Resources(cpu="1", mem="2Gi"),
            limits=Resources(cpu="2", mem="4Gi"),
        ),
    ),
    limits=Resources(cpu="1", mem="2Gi"),
    container_image=custom_image,
)
def dask_with_full_config(size: int) -> float:
    """Dask task with worker group, scheduler, custom images, and resource requests/limits."""
    array = da.random.random(size)
    return float(array.sum().compute())


@task(
    task_config=Dask(
        workers=WorkerGroup(
            number_of_workers=3,
            requests=Resources(cpu="1", mem="2Gi"),
            limits=Resources(cpu="2", mem="4Gi"),
        ),
        scheduler=Scheduler(
            requests=Resources(cpu="1", mem="1Gi"),
            limits=Resources(cpu="1", mem="2Gi"),
        ),
    ),
    limits=Resources(cpu="1", mem="2Gi"),
    container_image=custom_image,
)
def dask_with_scheduler_resources(size: int) -> float:
    """Dask task with scheduler resources configured."""
    array = da.random.random(size)
    return float(array.std().compute())


@workflow
def dask_workflow(size: int = 1000) -> float:
    basic = hello_dask(size=size)
    dask_with_full_config(size=size)
    dask_with_scheduler_resources(size=size)
    return basic


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(dask_workflow, size=1000)
    print(run.name)
    print(run.url)
