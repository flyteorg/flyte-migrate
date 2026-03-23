"""Transforms v1 flytekit.Resources into v2 flyte.Resources.

Handles merging of separate request/limit specifications, GPU/accelerator formatting,
and shared memory configuration.
"""

from typing import Literal, Optional, TypeVar, Union

import flyte
import flytekit
from flytekit.extras.accelerators import BaseAccelerator

ResourceValue = TypeVar("ResourceValue", str, int, float)


def _format_gpu(
    accelerator: Optional[BaseAccelerator],
    gpu_count: Optional[Union[str, int]],
) -> Optional[Union[str, int]]:
    """Format GPU specification from accelerator and GPU count.

    If an accelerator is provided, returns ``"<accelerator>:<count>"`` when a count
    is given, or just ``"<accelerator>"`` otherwise.  Falls back to the raw GPU
    count when no accelerator is specified.
    """
    if accelerator:
        return f"{accelerator}:{gpu_count}" if gpu_count else f"{accelerator}"
    if gpu_count:
        return str(gpu_count)
    return None


def _format_shared_memory(shared_memory: Optional[Union[Literal[True], str]]) -> Optional[str]:
    """Convert a v1 shared-memory specification to a v2 string value.

    ``True`` maps to ``"auto"``; an explicit string is passed through unchanged.
    """
    if shared_memory is True:
        return "auto"
    if isinstance(shared_memory, str):
        return shared_memory
    return None


def _transform_resource_v1_to_v2(
    requests: Optional[flytekit.Resources] = None,
    limits: Optional[flytekit.Resources] = None,
    resources: Optional[flytekit.Resources] = None,
    accelerator: Optional[BaseAccelerator] = None,
    shared_memory: Optional[Union[Literal[True], str]] = None,
) -> flyte.Resources:
    """Transform v1 resource specifications into a single v2 ``flyte.Resources``.

    Either *resources* **or** the *requests*/*limits* pair may be provided, but
    not both.  When *requests*/*limits* are used they are merged into a unified
    resource spec via :func:`_merge_flytekit_requests_and_limits_to_resources`.
    """
    if resources and (requests or limits):
        msg = "`resource` can not be used together with the `limits` or `requests`. Please only set `resource`."
        raise ValueError(msg)

    selected_resources = resources
    if not selected_resources:
        if not requests:
            requests = flytekit.Resources()
        if not limits:
            limits = flytekit.Resources()
        selected_resources = _merge_flytekit_requests_and_limits_to_resources(requests, limits)

    gpu = _format_gpu(accelerator, selected_resources.gpu)
    shm_value = _format_shared_memory(shared_memory)

    return flyte.Resources(
        cpu=selected_resources.cpu,
        memory=selected_resources.mem,
        gpu=gpu,  # type: ignore[arg-type]
        disk=selected_resources.ephemeral_storage,
        shm=shm_value,
    )


def set_resource_format(
    req: ResourceValue | None, lim: ResourceValue | None
) -> tuple[ResourceValue, ResourceValue] | ResourceValue | None:
    """Combine a request and limit value into the format expected by ``flytekit.Resources``.

    Returns a ``(request, limit)`` tuple when both are present, the single non-None
    value when only one is provided, or ``None`` when neither is set.
    """
    if req:
        if lim:
            return (req, lim)
        return req
    if lim:
        return lim
    return None


def _merge_flytekit_requests_and_limits_to_resources(
    requests: flytekit.Resources, limits: flytekit.Resources
) -> flytekit.Resources:
    """Merge separate request and limit objects into a single ``flytekit.Resources``."""
    return flytekit.Resources(
        cpu=set_resource_format(requests.cpu, limits.cpu),
        mem=set_resource_format(requests.mem, limits.mem),
        gpu=requests.gpu,
        ephemeral_storage=set_resource_format(requests.ephemeral_storage, limits.ephemeral_storage),
    )
