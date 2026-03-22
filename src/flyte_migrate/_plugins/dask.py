"""Dask plugin transformer: v1 ``flytekitplugins.dask.Dask`` -> v2 ``flyteplugins.dask.task.Dask``."""

from typing import Any, Optional

from flyte_migrate._resource import _transform_resource_v1_to_v2


def _transform_dask_config_v1_to_v2(v1_config: Optional[Any]) -> Optional[Any]:
    """Convert a v1 Dask config to its v2 equivalent.

    Translates worker group settings (count, image, resources) and scheduler
    settings (image, resources).

    Returns:
        A v2 ``Dask`` config, or ``None`` if *v1_config* is not the expected type.

    Raises:
        ModuleNotFoundError: If the required Dask plugin packages are missing.
    """
    try:
        from flytekitplugins.dask import Dask as v1DaskConfig
        from flyteplugins.dask.task import Dask as v2Dask
        from flyteplugins.dask.task import Scheduler as v2Scheduler
        from flyteplugins.dask.task import WorkerGroup as v2WorkerGroup
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(f"Dask plugin is not installed. Please ensure that {e.name} is installed.") from e

    if not isinstance(v1_config, v1DaskConfig):
        return None

    v1_workers = v1_config.workers
    v2_worker_group = v2WorkerGroup(
        number_of_workers=v1_workers.number_of_workers,
        image=v1_workers.image,
        resources=_transform_resource_v1_to_v2(requests=v1_workers.requests, limits=v1_workers.limits),
    )

    v1_scheduler = v1_config.scheduler
    v2_scheduler = v2Scheduler(
        image=v1_scheduler.image,
        resources=_transform_resource_v1_to_v2(requests=v1_scheduler.requests, limits=v1_scheduler.limits),
    )

    return v2Dask(
        workers=v2_worker_group,
        scheduler=v2_scheduler,
    )
