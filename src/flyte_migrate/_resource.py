from typing import Literal, Optional, Union, TypeVar

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
    if not requests:
        requests = flytekit.Resources()
    if not limits:
        limits = flytekit.Resources()

    # Handle GPU
    gpu = None
    if accelerator:
        if requests.gpu:
            gpu = f"{accelerator}:{requests.gpu}"
        else:
            gpu = f"{accelerator}"
    elif requests.gpu:
        gpu = str(requests.gpu)

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

    return flyte.Resources(
        cpu=set_resource_format(requests.cpu, limits.cpu),
        memory=set_resource_format(requests.mem, limits.mem),
        gpu=gpu,
        disk=(requests.ephemeral_storage, limits.ephemeral_storage)
        if requests.ephemeral_storage or limits.ephemeral_storage
        else None,
        shm=shared_memory,
    )
