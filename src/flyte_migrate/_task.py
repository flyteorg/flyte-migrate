"""Shim that replaces ``flytekit.task`` with a v1-compatible decorator backed by v2 internals.

The main entry point is :func:`task_shim`, which accepts the same keyword arguments as
the v1 ``@task`` decorator and translates them into a v2 ``TaskEnvironment`` + ``env.task``
call.  Heavy lifting (cache policy, resource merging, environment construction) is
delegated to focused helper functions so the top-level decorator stays readable.
"""

# Annotations below name flytekit.Cache, which only exists in newer flytekit. The shim is
# pip-installed into the user's own v1 image, whose flytekit we do not control, so keep
# annotations lazy — nothing here introspects them at runtime, and an eager
# ``Union[bool, flytekit.Cache]`` makes the whole module fail to import on older images
# with "AttributeError: module 'flytekit' has no attribute 'Cache'".
from __future__ import annotations

import datetime
from typing import Callable, Dict, List, Literal, Optional, ParamSpec, TypeVar, Union, cast

import flyte
import flytekit
from flyte._logging import logger
from flytekit.extras.accelerators import BaseAccelerator

from flyte_migrate._deploy import inherited_sys_path
from flyte_migrate._image import (
    _transform_image_spec_v1_to_v2,
    mirror_spec_onto,
    needs_pip_at_runtime,
    uses_pod_template,
    with_kubernetes_client,
)
from flyte_migrate._plugins import _transform_plugin_config_v1_to_v2
from flyte_migrate._pod_template import _transform_pod_template_v1_to_v2
from flyte_migrate._resource import _transform_resource_v1_to_v2
from flyte_migrate._secret import _transform_secret_v1_to_v2
from flyte_migrate._workflow import module_slug, parent_env_for

# Modules known to build a v1 PodTemplate at import time; every task env from one needs
# the kubernetes client, whichever task actually declared the template.
_pod_template_modules: set = set()

P = ParamSpec("P")  # capture the function's parameters
R = TypeVar("R")  # return type
T = TypeVar("T")  # task config

# ---------------------------------------------------------------------------
# Helpers — each responsible for one aspect of the v1 → v2 translation
# ---------------------------------------------------------------------------


def _translate_cache_policy(cache: Union[bool, flytekit.Cache]) -> Literal["auto", "disable"]:
    """Convert a v1 cache flag into the v2 cache policy string.

    In v1, ``cache=True`` enables caching while ``cache=False`` (the default) disables
    it.  The v2 API expects the strings ``"auto"`` or ``"disable"``.
    """
    return "auto" if cache else "disable"


def _build_task_environment(
    task_function: Callable,
    *,
    cache: Union[bool, flytekit.Cache],
    task_config: Optional[T],
    container_image: Optional[Union[str, flytekit.ImageSpec]],
    environment: Optional[Dict[str, str]],
    requests: Optional[flytekit.Resources],
    limits: Optional[flytekit.Resources],
    resources: Optional[flytekit.Resources],
    accelerator: Optional[BaseAccelerator],
    shared_memory: Optional[Union[Literal[True], str]],
    secret_requests: Optional[List[flytekit.Secret]],
    docs: Optional[flytekit.Documentation],
    pod_template: Optional[flytekit.PodTemplate],
    pod_template_name: Optional[str],
) -> flyte.TaskEnvironment:
    """Construct a v2 :class:`flyte.TaskEnvironment` from v1 task parameters.

    This is where the bulk of the v1 → v2 translation happens: resources, secrets,
    images, pod templates, plugin configs, and cache policy are all converted here.
    """
    image = _transform_image_spec_v1_to_v2(container_image)
    if task_function.__module__ in _pod_template_modules or uses_pod_template(pod_template, task_config):
        image = with_kubernetes_client(image)
    if needs_pip_at_runtime(task_config):
        image = image.with_pip_packages("pip")

    return flyte.TaskEnvironment(
        name=f"{module_slug(task_function.__module__)}_{task_function.__name__}_env",
        resources=_transform_resource_v1_to_v2(requests, limits, resources, accelerator, shared_memory),
        pod_template=_transform_pod_template_v1_to_v2(pod_template) or pod_template_name,
        secrets=_transform_secret_v1_to_v2(secret_requests),
        env_vars={**inherited_sys_path(), **(environment or {})} or None,
        image=image,
        cache=_translate_cache_policy(cache),
        plugin_config=_transform_plugin_config_v1_to_v2(task_config),
        description=docs.short_description if docs else None,
    )


def _register_task_environment(
    env: flyte.TaskEnvironment,
    container_image: Optional[Union[str, flytekit.ImageSpec]],
    module: Optional[str],
    pod_template: Optional[flytekit.PodTemplate] = None,
    task_config: object = None,
) -> None:
    """Wire a newly created environment into the parent workflow env of its own module."""
    parent = parent_env_for(module)
    if env not in parent.depends_on:
        parent.depends_on.append(env)
    mirror_spec_onto(parent, container_image)
    if uses_pod_template(pod_template, task_config):
        # Containers re-import the whole defining module, so a PodTemplate built anywhere in
        # it breaks the import for *every* task there, plus the parent workflow container —
        # not just the task that declared it. Backfill the ones already built, and remember
        # the module so later tasks in it get the client too.
        _pod_template_modules.add(module)
        parent.image = with_kubernetes_client(cast(flyte.Image, parent.image))
        for sibling in parent.depends_on:
            sibling.image = with_kubernetes_client(cast(flyte.Image, sibling.image))


# ---------------------------------------------------------------------------
# Public shim
# ---------------------------------------------------------------------------


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
    enable_deck: Optional[bool] = None,
    **kwargs,
):
    """Drop-in replacement for ``flytekit.task`` that bridges v1 arguments to v2.

    Supports both bare-decorator (``@task``) and parameterised (``@task(...)``) forms.
    Any unrecognised keyword arguments are logged and silently ignored so that new v1
    parameters do not break existing code.
    """
    if kwargs:
        logger.debug(f"Unsupported args {kwargs.values()}")

    def v2_decorator(_task_function: Optional[Callable[P, R]] = None) -> Callable[P, R]:
        if _task_function is None:
            raise ValueError("Task function cannot be None")

        env = _build_task_environment(
            _task_function,
            cache=cache,
            task_config=task_config,
            container_image=container_image,
            environment=environment,
            requests=requests,
            limits=limits,
            resources=resources,
            accelerator=accelerator,
            shared_memory=shared_memory,
            secret_requests=secret_requests,
            docs=docs,
            pod_template=pod_template,
            pod_template_name=pod_template_name,
        )
        _register_task_environment(env, container_image, _task_function.__module__, pod_template, task_config)
        return env.task(
            retries=retries,
            report=bool(enable_deck),
            timeout=timeout,
            interruptible=interruptible,
        )(_task_function)

    if _task_function is None:
        return v2_decorator
    return v2_decorator(_task_function)


flytekit.task = task_shim
