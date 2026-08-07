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


# --- Basic Ray task with a single worker group ---
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


# --- Ray task with multiple worker groups and autoscaling ---
@task(
    task_config=RayJobConfig(
        head_node_config=HeadNodeConfig(
            ray_start_params={"log-color": "True", "num-cpus": "0"},
            requests=Resources(cpu="1", mem="2Gi"),
            limits=Resources(cpu="2", mem="4Gi"),
        ),
        worker_node_config=[
            WorkerNodeConfig(
                group_name="cpu-workers",
                replicas=4,
                min_replicas=2,
                max_replicas=8,
                ray_start_params={"num-cpus": "4"},
                requests=Resources(cpu="2", mem="4Gi"),
                limits=Resources(cpu="4", mem="8Gi"),
            ),
            WorkerNodeConfig(
                group_name="gpu-workers",
                replicas=2,
                min_replicas=1,
                max_replicas=4,
                ray_start_params={"num-gpus": "0"},
            ),
        ],
        enable_autoscaling=True,
        runtime_env={"pip": ["numpy", "pandas"], "env_vars": {"RAY_DEDUP_LOGS": "0"}},
        shutdown_after_job_finishes=True,
        ttl_seconds_after_finished=300,
    ),
    limits=Resources(cpu="2", mem="2Gi"),
    container_image=custom_image,
)
def ray_autoscaling_task() -> typing.List[int]:
    futures = [f.remote(i) for i in range(10)]
    return ray.get(futures)


@workflow
def ray_workflow() -> typing.List[int]:
    res = ray_task()
    return res


@workflow
def ray_autoscaling_workflow() -> typing.List[int]:
    res = ray_autoscaling_task()
    return res


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    ctx = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG)

    print("--- Running basic ray workflow ---")
    run = ctx.run(ray_workflow)
    print(run.name)
    print(run.url)

    print("--- Running autoscaling ray workflow ---")
    run2 = ctx.run(ray_autoscaling_workflow)
    print(run2.name)
    print(run2.url)
