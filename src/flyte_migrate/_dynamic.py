"""Shim that replaces ``flytekit.dynamic`` with a v1-compatible decorator.

In v1, ``@dynamic`` is essentially a task that can spawn sub-tasks at runtime.  The v2
equivalent is a regular task, so this shim simply delegates to :func:`task_shim` with
the same keyword arguments.
"""

from typing import Callable, Union

import flytekit
from flyte._task import AsyncFunctionTaskTemplate, P, R

import flyte_migrate


def dynamic_shim(**kwargs) -> Union[AsyncFunctionTaskTemplate, Callable[P, R]]:
    """Drop-in replacement for ``flytekit.dynamic`` that delegates to :func:`task_shim`."""
    return flyte_migrate._task.task_shim(**kwargs)


flytekit.dynamic = dynamic_shim
