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

import importlib.metadata
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import flytekit
from flyte import Image, Resources, TaskEnvironment
from flyte._logging import logger

from flyte_migrate._resolver import MigrateTaskResolver


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


def _shim_requirements() -> Tuple[str, ...]:
    """``flyte-migrate`` plus a floor on ``flyte`` itself.

    Without the floor, a released ``flyte-migrate`` whose metadata caps ``flyte``
    (e.g. ``flyte<2.1``) makes the resolver *downgrade* the flyte already in the
    base image — 2.5.18 → 2.0.12 — and the shim then imports against the wrong
    runtime. Dev builds of flyte have no matching PyPI release, so skip the floor.
    """
    from flyte._version import __version__

    if "dev" in __version__:
        return (_flyte_migrate_requirement(),)
    return (_flyte_migrate_requirement(), f"flyte>={__version__}")


_parent_envs: Dict[str, TaskEnvironment] = {}


def _main_module_name() -> Optional[str]:
    """The name flyte will re-import the ``__main__`` script under, inside the container.

    ``flyte._module.extract_obj_module`` names a task's module by its path relative to the
    run's root dir, and ``flyte._initialize`` defaults that root dir to ``Path.cwd()``.
    Mirror both rules, so ``python examples/deck_example.py`` from the repo root yields
    ``examples.deck_example`` (matching the container's ``mod examples.deck_example``) while
    ``cd examples && python deck_example.py`` yields ``deck_example``.

    Env names are fixed at import time, before ``flyte.init`` runs, so cwd is the best
    available stand-in for the root dir — an explicitly-passed ``root_dir`` is not visible
    here.
    """
    main_file = getattr(sys.modules.get("__main__"), "__file__", None)
    if not main_file:
        return None
    path = Path(main_file).resolve()
    try:
        relative = path.relative_to(Path.cwd().resolve())
    except ValueError:
        # Outside the root dir; flyte falls back to the bare stem here too.
        return path.stem
    return ".".join(relative.with_suffix("").parts)


def module_slug(module: Optional[str]) -> str:
    """Turn a dotted module path into something usable in a v2 environment name.

    ``__main__`` is resolved to the name the container will import first. Running a file
    directly (``python examples/deck_example.py``) names environments at launch time off
    ``__main__``, but the remote resolver re-imports that file under its own name, so the
    container would look up ``deck_example_*`` in an image cache keyed ``main_*`` and fail
    with ``Environment '...' not found in image cache``.
    """
    if module == "__main__":
        module = _main_module_name()
    return re.sub(r"[^0-9a-zA-Z]+", "_", module or "main").strip("_")


def parent_env_for(module: Optional[str]) -> TaskEnvironment:
    """The parent workflow environment for *module*, created on first use."""
    name = f"{module_slug(module)}_workflow"
    env = _parent_envs.get(name)
    if env is None:
        env = TaskEnvironment(
            name=name,
            resources=Resources(cpu=0.8, memory="800Mi"),
            image=Image.from_debian_base().with_pip_packages("setuptools", "flytekit", *_shim_requirements()),
        )
        _parent_envs[name] = env
    return env


def workflow_shim(
    _workflow_function: Optional[Callable] = None,
    failure_policy: Any = None,
    interruptible: bool = False,
    on_failure: Any = None,
    docs: Any = None,
    pickle_untyped: bool = False,
    default_options: Any = None,
    **kwargs: Any,
) -> Any:
    """Drop-in replacement for ``flytekit.workflow``.

    Supports both the bare ``@workflow`` and parameterised ``@workflow(...)`` forms, and
    routes each function through the parent environment of the module that defines it.

    ``interruptible`` is forwarded to the v2 task.  The remaining v1-only parameters
    have no v2 equivalent (v2 workflows are plain Python — failures propagate as
    exceptions, so use ``try/except`` instead of ``failure_policy``/``on_failure``);
    they are logged and ignored rather than breaking the decorator.
    """
    dropped = {
        "failure_policy": failure_policy,
        "on_failure": on_failure,
        "docs": docs,
        "pickle_untyped": pickle_untyped,
        "default_options": default_options,
        **kwargs,
    }
    dropped_names = sorted(k for k, v in dropped.items() if v)
    if dropped_names:
        logger.warning(f"@workflow args not supported by flyte-migrate and ignored: {dropped_names}")

    def v2_decorator(fn: Callable) -> Any:
        tmpl = parent_env_for(fn.__module__).task(interruptible=interruptible or None)(fn)
        # Same reason as task_shim: the container must apply the shim before importing the user module.
        tmpl.task_resolver = MigrateTaskResolver()
        return tmpl

    if _workflow_function is None:
        return v2_decorator
    return v2_decorator(_workflow_function)


flytekit.workflow = workflow_shim
