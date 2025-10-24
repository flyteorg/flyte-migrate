import flyte_migrate  # noqa: F401, I001
import logging
import typing

import ray
from flytekit import task, workflow, ImageSpec, Resources
from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig, HeadNodeConfig

custom_image = ImageSpec(python_version="3.10", packages=["flytekitplugins-ray", "kubernetes"], apt_packages=["wget"])


@ray.remote
def f(x):
    return x * x


@task(
    task_config=RayJobConfig(
        head_node_config=HeadNodeConfig(ray_start_params={"log-color": "True"}),
        worker_node_config=[
            WorkerNodeConfig(
                group_name="test-group",
                replicas=2,
            )
        ],
    ),
    limits=Resources(cpu="2", mem="2Gi"),
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
