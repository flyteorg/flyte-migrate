"""Bridge v1 ``flytekit.current_context()`` reads to the v2 runtime context.

FlyteKit v1 code reads execution metadata through ``flytekit.current_context()``, which hands
back an ``ExecutionParameters``.  In v2 the same data lives on ``flyte.ctx()``.

Bridging this by patching ``ExecutionParameters.__getattr__`` does not work, and fails
silently.  ``__getattr__`` is only a *fallback* — Python consults it after normal lookup has
already raised ``AttributeError`` — and every attribute v1 code reaches for is a real
``@property`` on the class.  Lookup therefore always succeeds and the bridge never runs.
Nothing raises either, because flytekit's ``FlyteContextManager.initialize()`` pre-builds a
local-run safety net (``local/local/local`` identifiers, local temp paths) for running v1 code
outside a cluster, and the properties return *that* — well-formed, entirely fake, on a real
v2 cluster, with no error and no warning.

So the properties themselves are replaced here, in three groups:

* **backed by v2** — ``execution_id``, ``task_id``, ``raw_output_prefix``, ``logging``.
* **no v2 source** — ``stats``, ``execution_date``: warn once, then fall through to v1's local
  value.  v1 code usually only logs these, so raising would break workflows that otherwise run
  fine; the warning is what makes the gap visible.
* **left alone** — ``working_directory``.  v1's contract is "a local scratch directory for this
  task", and a local temp directory is exactly that, so the fallback is already correct.  This
  is unlike ``raw_output_prefix``, whose contract is a blob-store prefix — there a local path is
  a real error that silently discards the task's output when the pod exits.

``__getattr__`` is still patched, but scoped to what it was ever able to serve: task-type
specific context, which v1 plugins stash in ``_attrs`` under an upper-cased key (Spark's
session being the canonical case).
"""

from typing import Any

import flyte
from flyte._logging import logger
from flytekit import ExecutionParameters
from flytekit.models.core import identifier as _identifier

_warned: set = set()


def _warn_once(key: str, message: str) -> None:
    """Warn the first time only — these are read inside loops as often as not."""
    if key not in _warned:
        _warned.add(key)
        logger.warning(message)


def _active_task_context() -> Any:
    """The live v2 task context.

    ``flyte.ctx()`` returns ``NULL_TASK_CONTEXT`` — falsy, but *not* ``None`` — when there is no
    task running, so this has to be a truthiness check.  An ``is None`` guard passes straight
    through and the caller then explodes on ``None``'s attributes.
    """
    tctx = flyte.ctx()
    if not tctx:
        raise RuntimeError(
            "No active Flyte context found. Make sure you are inside a Flyte task or workflow execution."
        )
    return tctx


# ---------------------------------------------------------------------------
# Backed by v2
# ---------------------------------------------------------------------------


def _execution_id(self: ExecutionParameters) -> _identifier.WorkflowExecutionIdentifier:
    """v1's execution id, from the v2 action.

    ``run_name`` is the right field, not ``name``: v1's ``execution_id`` identifies the whole
    execution, while ``ActionID.name`` identifies one task invocation within it.  Mapping it to
    ``name`` would hand every task a different id and quietly break the main use of this value —
    a run-level key for correlation, dedup and idempotency.
    """
    action = _active_task_context().action
    return _identifier.WorkflowExecutionIdentifier(
        project=action.project,
        domain=action.domain,
        name=action.run_name,
    )


def _task_id(self: ExecutionParameters) -> _identifier.Identifier:
    """v1's task id.  Here ``ActionID.name`` *is* the right field — see :func:`_execution_id`."""
    tctx = _active_task_context()
    action = tctx.action
    return _identifier.Identifier(
        _identifier.ResourceType.TASK,
        action.project,
        action.domain,
        action.name,
        tctx.version,
    )


def _raw_output_prefix(self: ExecutionParameters) -> str:
    """Where offloaded data belongs.  The costliest of the group to get wrong: v1's local
    fallback is a container-local temp dir, so writes succeed and then vanish with the pod."""
    return _active_task_context().raw_data_path.path


def _logging(self: ExecutionParameters) -> Any:
    return logger


# ---------------------------------------------------------------------------
# No v2 source — degrade loudly rather than silently
# ---------------------------------------------------------------------------


def _stats(self: ExecutionParameters) -> Any:
    """v2 has no statsd-style metrics interface, so this stays v1's no-op ``MockStats``."""
    _warn_once(
        "stats",
        "flytekit.current_context().stats has no v2 equivalent; metrics emitted through it are discarded.",
    )
    return self._stats


def _execution_date(self: ExecutionParameters) -> Any:
    """v2's ``TaskContext`` carries no timestamp, so this stays v1's value — the moment the
    context was initialised, which is close to but not the task's execution date.  Close enough
    to look right in a log line, wrong enough to collapse date-partitioned output."""
    _warn_once(
        "execution_date",
        "flytekit.current_context().execution_date has no v2 equivalent; "
        "returning the time the context was initialised, not the task's execution date.",
    )
    return self._execution_date


# ---------------------------------------------------------------------------
# Task-type specific context — the one thing __getattr__ can serve
# ---------------------------------------------------------------------------


def _get_attrs(self: ExecutionParameters, attr_name: str) -> Any:
    """Resolve a name that has no property on the class.

    v1 plugins stash task-type specific context in ``_attrs`` under an upper-cased key (Spark's
    session, for one), so that is checked first; the v2 context's user-data bag is the fallback.

    Missing names must raise ``AttributeError``.  ``__getattr__`` raising anything else escapes
    ``hasattr`` and ``getattr(..., default)``, which only catch ``AttributeError`` — so v1's
    common ``if hasattr(ctx, "spark_session")`` guard would blow up instead of returning False.
    """
    attrs = getattr(self, "_attrs", None)
    if attrs and attr_name.upper() in attrs:
        return attrs[attr_name.upper()]

    tctx = flyte.ctx()
    data = tctx.data if tctx else None
    if data and attr_name in data:
        return data[attr_name]

    raise AttributeError(f"{attr_name} not available as a parameter in Flyte context - are you in right task-type?")


ExecutionParameters.execution_id = property(_execution_id)  # type: ignore[assignment]
ExecutionParameters.task_id = property(_task_id)  # type: ignore[assignment]
ExecutionParameters.raw_output_prefix = property(_raw_output_prefix)  # type: ignore[assignment]
ExecutionParameters.logging = property(_logging)  # type: ignore[assignment]
ExecutionParameters.stats = property(_stats)  # type: ignore[assignment]
ExecutionParameters.execution_date = property(_execution_date)  # type: ignore[assignment]
ExecutionParameters.__getattr__ = _get_attrs  # type: ignore[assignment]
