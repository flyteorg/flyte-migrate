"""Shim that replaces ``flytekit.reference_task`` with a v2-compatible decorator.

In v1, ``@reference_task(project, domain, name, version)`` creates a ``ReferenceTask``
that points to a task already registered on the Flyte cluster.  The decorated function
serves as an interface stub — its body is never executed.

In v2, the equivalent is ``flyte.remote.TaskDetails.get(name, project, domain, version)``
which returns a ``LazyEntity`` that fetches the remote task on first call.

This module provides a drop-in ``reference_task`` decorator that transparently
creates a v2 ``LazyEntity`` from the v1 parameters.
"""

from typing import Any, Callable

import flytekit
from flyte.remote._task import TaskDetails


def reference_task_shim(
    project: str,
    domain: str,
    name: str,
    version: str,
) -> Callable:
    """Drop-in replacement for ``flytekit.reference_task``.

    Returns a decorator that ignores the stub function body and instead returns
    a v2 ``LazyEntity`` pointing to the remote task.
    """

    def wrapper(fn: Callable[..., Any]) -> Any:
        return TaskDetails.get(
            name=name,
            project=project,
            domain=domain,
            version=version,
        )

    return wrapper


flytekit.reference_task = reference_task_shim
