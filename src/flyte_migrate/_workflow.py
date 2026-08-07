"""Shim that replaces ``flytekit.workflow`` with a v2 task-based workflow decorator.

In Flyte v2, workflows are expressed as tasks within a parent
:class:`flyte.TaskEnvironment`.  This module creates that parent environment with
sensible defaults (minimal CPU/memory, a Debian base image with ``flytekit`` installed)
and patches ``flytekit.workflow`` to route through it.

All child task environments created by :mod:`flyte_migrate._task` register themselves
as dependencies of ``parent_env`` via ``parent_env.depends_on``.
"""

import importlib.metadata
import re

import flytekit
from flyte import Image, Resources, TaskEnvironment


def _flyte_migrate_requirement() -> str:
    """Pip requirement that makes ``import flyte_migrate`` resolve inside remote containers.

    Pinned to the installed release; dev/local versions (e.g. ``0.1.dev3+g1234``)
    don't exist on PyPI, so fall back to unpinned — for dev runs the code bundle's
    synced sys.path shadows the installed copy anyway.
    """
    try:
        version = importlib.metadata.version("flyte-migrate")
    except importlib.metadata.PackageNotFoundError:
        return "flyte-migrate"
    return f"flyte-migrate=={version}" if re.fullmatch(r"[\d.]+", version) else "flyte-migrate"


parent_env = TaskEnvironment(
    name="flytekit_workflow",
    resources=Resources(cpu=0.8, memory="800Mi"),
    image=Image.from_debian_base().with_pip_packages("setuptools", "flytekit", _flyte_migrate_requirement()),
)


def _workflow_shim(*args, **kwargs):
    """``parent_env.task`` that stamps the shim-aware resolver onto the template.

    Remote pods must apply the shim before importing the user module (which may lack
    the ``import flyte_migrate`` line when driven by the CLI or upgrade flow).
    """
    from flyte._task import TaskTemplate

    from flyte_migrate._resolver import ShimTaskResolver

    out = parent_env.task(*args, **kwargs)
    if isinstance(out, TaskTemplate):  # bare @workflow form
        out.task_resolver = ShimTaskResolver()
        return out

    def decorator(fn):  # parameterised @workflow(...) form
        template = out(fn)
        template.task_resolver = ShimTaskResolver()
        return template

    return decorator


flytekit.workflow = _workflow_shim
