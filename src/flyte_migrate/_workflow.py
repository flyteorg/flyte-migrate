"""Shim that replaces ``flytekit.workflow`` with a v2 task-based workflow decorator.

In Flyte v2, workflows are expressed as tasks within a parent
:class:`flyte.TaskEnvironment`. There is one parent environment **per defining module**,
named after it — ``examples.hello`` gets ``examples_hello_workflow``, so its ``wf``
registers as ``examples_hello_workflow.wf``.

Namespacing by module is what keeps two examples that both define ``wf`` (or both define
a task called ``say_hello``) from colliding. A single global parent environment meant the
second import silently overwrote the first, and v2's environment discovery rejected the
duplicate name outright with ``Duplicate environment name ... found``.

Child task environments created by :mod:`flyte_migrate._task` register themselves as
dependencies of their own module's parent via ``depends_on``.
"""

import re
from typing import Any, Callable, Dict, Optional

import flytekit
from flyte import Image, Resources, TaskEnvironment

_parent_envs: Dict[str, TaskEnvironment] = {}


def module_slug(module: Optional[str]) -> str:
    """Turn a dotted module path into something usable in a v2 environment name."""
    return re.sub(r"[^0-9a-zA-Z]+", "_", module or "main").strip("_")


def parent_env_for(module: Optional[str]) -> TaskEnvironment:
    """The parent workflow environment for *module*, created on first use."""
    name = f"{module_slug(module)}_workflow"
    env = _parent_envs.get(name)
    if env is None:
        env = TaskEnvironment(
            name=name,
            resources=Resources(cpu=0.8, memory="800Mi"),
            image=Image.from_debian_base().with_pip_packages("setuptools", "flytekit"),
        )
        _parent_envs[name] = env
    return env


def workflow_shim(_workflow_function: Optional[Callable] = None, **kwargs: Any) -> Any:
    """Drop-in replacement for ``flytekit.workflow``.

    Supports both the bare ``@workflow`` and parameterised ``@workflow(...)`` forms, and
    routes each function through the parent environment of the module that defines it.
    """

    def v2_decorator(fn: Callable) -> Any:
        return parent_env_for(fn.__module__).task(**kwargs)(fn)

    if _workflow_function is None:
        return v2_decorator
    return v2_decorator(_workflow_function)


flytekit.workflow = workflow_shim
