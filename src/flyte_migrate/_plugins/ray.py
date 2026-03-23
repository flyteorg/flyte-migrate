"""Ray plugin transformer: v1 ``flytekitplugins.ray.RayJobConfig`` -> v2 ``flyteplugins.ray.task.RayJobConfig``."""

from typing import Any, Optional

from flyte_migrate._pod_template import _transform_pod_template_v1_to_v2
from flyte_migrate._resource import _transform_resource_v1_to_v2


def _transform_ray_config_v1_to_v2(v1_config: Optional[Any]) -> Optional[Any]:
    """Convert a v1 Ray job config to its v2 equivalent.

    Translates head node, worker node (including autoscaling and pod templates),
    and top-level Ray job settings.

    Returns:
        A v2 ``RayJobConfig``, or ``None`` if *v1_config* is not the expected type.

    Raises:
        ModuleNotFoundError: If the required Ray plugin packages are missing.
    """
    try:
        from flytekitplugins.ray import RayJobConfig as v1RayConfig
        from flyteplugins.ray.task import HeadNodeConfig as v2HeadNodeConfig
        from flyteplugins.ray.task import RayJobConfig as v2RayConfig
        from flyteplugins.ray.task import WorkerNodeConfig as v2WorkerNodeConfig
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(f"Ray plugin is not installed. Please ensure that {e.name} is installed.") from e

    if not isinstance(v1_config, v1RayConfig):
        return None

    v2_worker_node_configs = [
        v2WorkerNodeConfig(
            group_name=v1_worker.group_name,
            replicas=v1_worker.replicas,
            min_replicas=v1_worker.min_replicas,
            max_replicas=v1_worker.max_replicas,
            ray_start_params=v1_worker.ray_start_params,
            pod_template=_transform_pod_template_v1_to_v2(v1_worker.pod_template),
            requests=_transform_resource_v1_to_v2(resources=v1_worker.requests),
            limits=_transform_resource_v1_to_v2(resources=v1_worker.limits),
        )
        for v1_worker in v1_config.worker_node_config
    ]

    v2_head_node_config = None
    if v1_config.head_node_config:
        v1_head = v1_config.head_node_config
        v2_head_node_config = v2HeadNodeConfig(
            ray_start_params=v1_head.ray_start_params,
            pod_template=_transform_pod_template_v1_to_v2(v1_head.pod_template),
            requests=_transform_resource_v1_to_v2(v1_head.requests),
            limits=_transform_resource_v1_to_v2(v1_head.limits),
        )

    return v2RayConfig(
        worker_node_config=v2_worker_node_configs,
        head_node_config=v2_head_node_config,
        enable_autoscaling=v1_config.enable_autoscaling,
        runtime_env=v1_config.runtime_env,
        address=v1_config.address,
        shutdown_after_job_finishes=v1_config.shutdown_after_job_finishes,
        ttl_seconds_after_finished=v1_config.ttl_seconds_after_finished,
    )
