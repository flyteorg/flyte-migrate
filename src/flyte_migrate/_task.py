import datetime
from typing import Callable, Dict, List, Literal, Optional, ParamSpec, TypeVar, Union

import flyte
import flytekit
from flyte._logging import logger
from flytekit.extras.accelerators import BaseAccelerator

from flyte_migrate._image import _transform_image_spec_v1_to_v2
from flyte_migrate._plugins import _transform_plugin_config_v1_to_v2
from flyte_migrate._pod_template import _transform_pod_template_v1_to_v2
from flyte_migrate._resource import _transform_resource_v1_to_v2
from flyte_migrate._secret import _transform_secret_v1_to_v2
from flyte_migrate._workflow import parent_env

P = ParamSpec("P")  # capture the function's parameters
R = TypeVar("R")  # return type
T = TypeVar("T")  # task config

# Map a v1 task to one of the v2 env
_task_to_env: Dict[str, flyte.TaskEnvironment] = {}


def task_shim(
    _task_function: Optional[Callable[P, R]] = None,
    task_config: Optional[T] = None,
    cache: Union[bool, flytekit.Cache] = False,
    retries: int = 0,
    interruptible: Optional[bool] = None,
    timeout: Union[datetime.timedelta, int] = 0,
    container_image: Optional[Union[str, flytekit.ImageSpec]] = None,
    environment: Optional[Dict[str, str]] = None,
    requests: Optional[flytekit.Resources] = None,
    limits: Optional[flytekit.Resources] = None,
    resources: Optional[flytekit.Resources] = None,
    accelerator: Optional[BaseAccelerator] = None,
    shared_memory: Optional[Union[Literal[True], str]] = None,
    secret_requests: Optional[List[flytekit.Secret]] = None,
    docs: Optional[flytekit.Documentation] = None,
    pod_template: Optional[flytekit.PodTemplate] = None,
    pod_template_name: Optional[str] = None,
    # labels: Optional[dict[str, str]] = None,
    # annotations: Optional[dict[str, str]] = None,
    **kwargs,
):
    if kwargs:
        logger.debug(f"Unsupported args {kwargs.values()}")

    def v2_decorator(_task_function: Optional[Callable[P, R]] = None) -> Callable[P, R]:
        env = flyte.TaskEnvironment(
            name=_task_function.__name__ + "_env",
            resources=_transform_resource_v1_to_v2(requests, limits, resources, accelerator, shared_memory),
            pod_template=_transform_pod_template_v1_to_v2(pod_template) or pod_template_name,
            secrets=_transform_secret_v1_to_v2(secret_requests),
            env_vars=environment,
            image=_transform_image_spec_v1_to_v2(container_image),
            cache="auto" if cache else "disable",
            plugin_config=_transform_plugin_config_v1_to_v2(task_config),
            description=docs.short_description if docs else None,
        )
        parent_env.depends_on.append(env)
        _task_to_env[_transform_image_spec_v1_to_v2(container_image)] = env
        return env.task(_task_function, retries=retries, timeout=timeout, interruptible=interruptible)

    if _task_function is None:
        return v2_decorator
    return v2_decorator(_task_function)


flytekit.task = task_shim
