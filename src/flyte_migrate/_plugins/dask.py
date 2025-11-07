from typing import Any, Optional

from flyte_migrate._resource import _transform_resource_v1_to_v2


def _transform_dask_config_v1_to_v2(v1_config: Optional[Any]) -> Optional[Any]:
    try:
        from flytekitplugins.dask import Dask as v1DaskConfig
        from flyteplugins.dask.task import Dask as v2Dask
        from flyteplugins.dask.task import WorkerGroup as v2WorkerGroup
        from flyteplugins.dask.task import Scheduler as v2Scheduler
    except ModuleNotFoundError:
        return None

    if not isinstance(v1_config, v1DaskConfig):
        return None

    # Get the worker group instance from the v1 config
    v1_worker_group = v1_config.workers
    
    v2_worker_group = v2WorkerGroup(
        number_of_workers=v1_worker_group.number_of_workers,
        image=v1_worker_group.image,
        resources=_transform_resource_v1_to_v2(requests=v1_worker_group.requests, limits=v1_worker_group.limits),
    )

    # Get the scheduler instance from the v1 config
    v1_scheduler = v1_config.scheduler
    
    v2_scheduler = v2Scheduler(
        image=v1_scheduler.image,
        resources=_transform_resource_v1_to_v2(requests=v1_scheduler.requests, limits=v1_scheduler.limits),
    )

    return v2Dask(
        workers=v2_worker_group,
        scheduler=v2_scheduler,
    )
