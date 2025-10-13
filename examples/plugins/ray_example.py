import flyte_migrate  # noqa: F401, I001
import logging
import typing

import ray
from flytekit import task, workflow, ImageSpec, Resources
from flytekitplugins.ray import HeadNodeConfig, RayJobConfig, WorkerNodeConfig

custom_image = ImageSpec(python_version="3.10", packages=["flytekitplugins-ray"])


@ray.remote
def f(x):
    return x * x


@task(
    task_config=RayJobConfig(
        worker_node_config=[
            WorkerNodeConfig(
                group_name="test-group",
                requests=Resources(mem="1Gi"),
                limits=Resources(mem="1Gi"),
                replicas=2,
            )
        ],
        head_node_config=HeadNodeConfig(
            requests=Resources(mem="1Gi"),
            limits=Resources(mem="1Gi"),
        ),
    ),
    limits=Resources(mem="4Gi"),
    container_image=custom_image,
)
def ray_task() -> typing.List[int]:
    futures = [f.remote(i) for i in range(5)]
    return ray.get(futures)


@workflow
def ray_workflow() -> typing.List[int]:
    res = ray_task()
    return res


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(ray_workflow)
    print(run.name)
    print(run.url)
