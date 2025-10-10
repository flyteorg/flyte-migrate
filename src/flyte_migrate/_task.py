import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Literal, Optional, Tuple, Union, TYPE_CHECKING


import flyte
from flyte._doc import Documentation
from flyte._task import AsyncFunctionTaskTemplate, P, R
from flytekit import Cache, Resources, Secret, ImageSpec, Documentation, PodTemplate
from flytekit.core.base_task import T, TaskResolverMixin
from flytekit.core.python_function_task import PythonFunctionTask
from flytekit.core.task import FuncOut
from flytekit.deck import DeckField
from flytekit.extras.accelerators import BaseAccelerator

import flytekit

from flyte_migrate._image import _transform_image_spec_v1_to_v2
from flyte_migrate._workflow import parent_env


# Map a v1 task to one of the v2 env
_task_to_env: Dict[str, flyte.TaskEnvironment] = {}


def task_shim(
    _task_function: Optional[Callable[P, "FuncOut"]] = None,
    task_config: Optional["T"] = None,
    cache: Union[bool, "Cache"] = False,
    retries: int = 0,
    interruptible: Optional[bool] = None,
    deprecated: str = "",
    timeout: Union[datetime.timedelta, int] = 0,
    container_image: Optional[Union[str, "ImageSpec"]] = None,
    environment: Optional[Dict[str, str]] = None,
    requests: Optional[Resources] = None,
    limits: Optional[Resources] = None,
    secret_requests: Optional[List["Secret"]] = None,
    docs: Optional["Documentation"] = None,
    disable_deck: Optional[bool] = None,
    enable_deck: Optional[bool] = None,
    pod_template: Optional["PodTemplate"] = None,
    pod_template_name: Optional[str] = None,
    accelerator: Optional["BaseAccelerator"] = None,
    pickle_untyped: bool = False,
    shared_memory: Optional[Union[Literal[True], str]] = None,
    resources: Optional[Resources] = None,
    labels: Optional[dict[str, str]] = None,
    annotations: Optional[dict[str, str]] = None,
    **kwargs,
) -> Union[AsyncFunctionTaskTemplate, Callable[P, R]]:
    plugin_config = task_config
    pod_template = (
        flyte.PodTemplate(
            pod_spec=pod_template.pod_spec,
            primary_container_name=pod_template.primary_container_name,
            labels=pod_template.labels,
            annotations=pod_template.annotations,
        )
        if pod_template
        else None
    )

    docs = Documentation(description=docs.description) if docs else None
    v2_image = _transform_image_spec_v1_to_v2(container_image)

    if v2_image.uri in _task_to_env:
        # TODO: Key should be a hash of the task
        v2_task = _task_to_env[v2_image.uri].task
    else:
        env = flyte.TaskEnvironment(
            name="flyte-task_" + v2_image._final_tag,
            resources=flyte.Resources(cpu=0.8, memory="800Mi"),
            image=v2_image,
            cache="auto" if cache else "disable",
            plugin_config=plugin_config,
        )
        parent_env.depends_on.append(env)
        _task_to_env[v2_image.uri] = env
        v2_task = env.task
    return v2_task(retries=retries, pod_template=pod_template_name or pod_template, docs=docs)


flytekit.task = task_shim
