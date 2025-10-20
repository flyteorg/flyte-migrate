from typing import Literal, Optional, TypeVar, Union

import flyte
import flytekit
from flytekit.extras.accelerators import BaseAccelerator

ResourceValue = TypeVar("ResourceValue", str, int, float)


def _transform_resource_v1_to_v2(
    requests: Optional[flytekit.Resources] = None,
    limits: Optional[flytekit.Resources] = None,
    resources: Optional[flytekit.Resources] = None,
    accelerator: Optional[BaseAccelerator] = None,
    shared_memory: Optional[Union[Literal[True], str]] = None,
):
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

    # Parse GPU
    gpu = None
    if accelerator:
        if selected_resources.gpu:
            gpu = f"{accelerator}:{selected_resources.gpu}"
        else:
            gpu = f"{accelerator}"
    elif selected_resources.gpu:
        gpu = str(selected_resources.gpu)

    return flyte.Resources(
        cpu=selected_resources.cpu,
        memory=selected_resources.mem,
        gpu=gpu,
        disk=selected_resources.ephemeral_storage,
        shm=shared_memory,
    )


def set_resource_format(
    req: ResourceValue | None, lim: ResourceValue | None
) -> tuple[ResourceValue, ResourceValue] | ResourceValue | None:
    if req:
        if lim:
            return (req, lim)
        return req
    elif lim:
        return lim
    else:
        return None


def _merge_flytekit_requests_and_limits_to_resources(requests, limits: flytekit.Resources) -> flytekit.Resources:
    """
    Merge the requests and limits into resources.
    """
    target_resources = flytekit.Resources(
        cpu=set_resource_format(requests.cpu, limits.cpu),
        mem=set_resource_format(requests.mem, limits.mem),
        gpu=requests.gpu,
        ephemeral_storage=set_resource_format(requests.ephemeral_storage, limits.ephemeral_storage),
    )
    return target_resources
