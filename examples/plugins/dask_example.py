import flyte_migrate  # noqa: F401, I001
import logging
import typing

from dask import array as da
from flytekit import task, workflow, ImageSpec, Resources
from flytekitplugins.dask import Dask, WorkerGroup

custom_image = ImageSpec(python_version="3.10", packages=["flytekitplugins-dask", "numpy"])

if custom_image.is_container():
    from dask import array as da
    from flytekitplugins.dask import Dask, WorkerGroup


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
    # Dask will automatically generate a client in the background using the Client() function.
    # When running remotely, the Client() function will utilize the deployed Dask cluster.
    array = da.random.random(size)
    return float(array.mean().compute())

if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(hello_dask, size=1000)
    print(run.name)
    print(run.url)