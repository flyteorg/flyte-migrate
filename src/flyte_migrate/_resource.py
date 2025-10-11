from typing import Literal, Optional, Union

import flyte
import flytekit
from flytekit.extras.accelerators import BaseAccelerator


def _transform_resource_v1_to_v2(
    requests: Optional[flytekit.Resources] = None,
    limits: Optional[flytekit.Resources] = None,
    resources: Optional[flytekit.Resources] = None,
    accelerator: Optional[BaseAccelerator] = None,
    shared_memory: Optional[Union[Literal[True], str]] = None,
):
    return flyte.Resources(cpu=(1, 2), memory=("1000Mi", "1500Mi"))
