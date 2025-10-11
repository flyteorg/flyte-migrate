from typing import Callable, Union

import flytekit
from flyte._task import AsyncFunctionTaskTemplate, P, R

import flyte_migrate


def dynamic_shim(**kwargs) -> Union[AsyncFunctionTaskTemplate, Callable[P, R]]:
    return flyte_migrate._task.task_shim(**kwargs)


flytekit.dynamic = dynamic_shim
