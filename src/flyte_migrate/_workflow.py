"""Shim that replaces ``flytekit.workflow`` with a v2 task-based workflow decorator.

In Flyte v2, workflows are expressed as tasks within a parent
:class:`flyte.TaskEnvironment`.  This module creates that parent environment with
sensible defaults (minimal CPU/memory, a Debian base image with ``flytekit`` installed)
and patches ``flytekit.workflow`` to route through it.

All child task environments created by :mod:`flyte_migrate._task` register themselves
as dependencies of ``parent_env`` via ``parent_env.depends_on``.
"""

import flytekit
from flyte import Image, Resources, TaskEnvironment

parent_env = TaskEnvironment(
    name="flytekit_workflow",
    resources=Resources(cpu=0.8, memory="800Mi"),
    image=Image.from_debian_base().with_pip_packages("setuptools", "flytekit"),
)

flytekit.workflow = parent_env.task
