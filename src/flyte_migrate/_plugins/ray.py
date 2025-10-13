from typing import Any, Optional

from flyte_migrate._pod_template import _transform_pod_template_v1_to_v2


def _transform_ray_config_v1_to_v2(v1_config: Optional[Any]) -> Optional[Any]:
    try:
        from flytekitplugins.ray import RayJobConfig as v1RayConfig
        from flyteplugins.ray.task import HeadNodeConfig as v2HeadNodeConfig
        from flyteplugins.ray.task import RayJobConfig as v2RayConfig
        from flyteplugins.ray.task import WorkerNodeConfig as v2WorkerNodeConfig
    except ModuleNotFoundError:
        return None

    if not isinstance(v1_config, v1RayConfig):
        return None

    v2_worker_node_configs = [
        v2WorkerNodeConfig(
            group_name=v1_worker_node_config.group_name,
            replicas=v1_worker_node_config.replicas,
            min_replicas=v1_worker_node_config.min_replicas,
            max_replicas=v1_worker_node_config.max_replicas,
            ray_start_params=v1_worker_node_config.ray_start_params,
            pod_template=_transform_pod_template_v1_to_v2(v1_worker_node_config.pod_template),
            requests=v1_worker_node_config.requests,
            limits=v1_worker_node_config.limits,
        )
        for v1_worker_node_config in v1_config.worker_node_config
    ]

    v2_head_node_config = None
    if v1_config.head_node_config:
        v2_head_node_config = v2HeadNodeConfig(
            ray_start_params=v1_config.head_node_config.ray_start_params,
            pod_template=_transform_pod_template_v1_to_v2(v1_config.head_node_config.pod_template),
            requests=v1_config.head_node_config.requests,
            limits=v1_config.head_node_config.limits,
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
