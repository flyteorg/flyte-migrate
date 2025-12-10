from typing import Any, Optional


def _transform_pytorch_config_v1_to_v2(v1_config: Optional[Any]) -> Optional[Any]:
    try:
        from flytekitplugins.kfpytorch import Elastic as v1Elastic
        from flyteplugins.pytorch.task import Elastic as v2Elastic
        from flyteplugins.pytorch.task import RunPolicy as v2RunPolicy

    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            f"\nPyTorch plugin is not installed. \nPlease ensure that {e.name} is installed."
        ) from e

    if not isinstance(v1_config, v1Elastic):
        return None

    run_policy = None
    if v1_config.run_policy is not None and v1_config.run_policy.clean_pod_policy is not None:
        run_policy = v2RunPolicy(
            # flytesdk will capitalize the enum names, so we access the name attribute
            clean_pod_policy=v1_config.run_policy.clean_pod_policy.name,
            ttl_seconds_after_finished=v1_config.run_policy.ttl_seconds_after_finished,
            active_deadline_seconds=v1_config.run_policy.active_deadline_seconds,
            backoff_limit=v1_config.run_policy.backoff_limit,
        )

    return v2Elastic(
        nnodes=v1_config.nnodes,
        nproc_per_node=v1_config.nproc_per_node,
        run_policy=run_policy,
        monitor_interval=v1_config.monitor_interval,
        max_restarts=v1_config.max_restarts,
        rdzv_configs=v1_config.rdzv_configs,
    )
