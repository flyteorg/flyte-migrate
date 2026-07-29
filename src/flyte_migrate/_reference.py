"""Shim that replaces ``flytekit.reference_task`` with a v2-compatible decorator.

In v1, ``@reference_task(project, domain, name, version)`` creates a ``ReferenceTask``
that points to a task already registered on the Flyte cluster.  The decorated function
serves as an interface stub — its body is never executed.

In v2, the equivalent is ``flyte.remote.TaskDetails.get(name, project, domain, version)``
which returns a ``LazyEntity`` that fetches the remote task on first call.

This module provides a drop-in ``reference_task`` decorator that transparently
creates a v2 ``LazyEntity`` from the v1 parameters, wrapped so that synchronous
workflow callers get a resolved result instead of a bare coroutine.
"""

from typing import Any, Callable

import flytekit
from flyte.remote._task import LazyEntity, TaskDetails


class _SyncLazyEntity:
    """Wrapper around :class:`LazyEntity` that makes ``__call__`` sync-safe.

    ``LazyEntity.__call__`` is ``async def``, so calling it from a synchronous
    v1-style workflow returns a coroutine object instead of the actual result.
    This wrapper delegates attribute access to the underlying ``LazyEntity`` but
    overrides ``__call__`` to eagerly fetch the ``TaskDetails`` (via the already-
    syncified ``fetch()``) and then call it — which also uses the controller's
    ``submit_task_ref`` under the hood.
    """

    def __init__(self, entity: LazyEntity) -> None:
        self._entity = entity

    @property
    def name(self) -> str:
        return self._entity.name

    def fetch(self) -> TaskDetails:
        return self._entity.fetch()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # LazyEntity.__call__ is async. Use the flyte syncify background loop
        # to run it synchronously — the same mechanism used by LazyEntity.fetch().
        from flyte.syncify import syncify

        coro = self._entity(*args, **kwargs)
        return syncify._bg_loop.call_in_loop_sync(coro)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._entity, item)

    def __repr__(self) -> str:
        return repr(self._entity)


def reference_task_shim(
    project: str,
    domain: str,
    name: str,
    version: str | None = None,
) -> Callable:
    """Drop-in replacement for ``flytekit.reference_task``.

    Returns a decorator that ignores the stub function body and instead returns
    a sync-safe wrapper around a v2 ``LazyEntity`` pointing to the remote task.

    Unlike v1, ``version`` may be omitted — the latest registered version of the
    task is then resolved at call time (v2 ``auto_version="latest"``).
    """

    def wrapper(fn: Callable[..., Any]) -> Any:
        entity = TaskDetails.get(
            name=name,
            project=project,
            domain=domain,
            version=version,
            auto_version="latest" if version is None else None,
        )
        return _SyncLazyEntity(entity)

    return wrapper


def reference_launch_plan_shim(
    project: str,
    domain: str,
    name: str,
    version: str | None = None,
) -> Callable:
    """Drop-in replacement for ``flytekit.reference_launch_plan``.

    v2 has no launch plan entity — v1 workflows register as tasks in the
    ``flytekit_workflow`` environment, so ``name`` must be
    ``flytekit_workflow.<workflow_name>``. Otherwise identical to
    :func:`reference_task_shim`.
    """
    return reference_task_shim(project, domain, name, version)


flytekit.reference_task = reference_task_shim
flytekit.reference_launch_plan = reference_launch_plan_shim
