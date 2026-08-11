"""Shim v1 ``flytekit.ContainerTask`` onto v2 ``flyte.extras.ContainerTask``.

v2 has a near-identical raw-container task; this factory translates the v1 constructor
arguments (resources, secrets, pod templates, TaskMetadata, metadata format enum) and
registers the resulting task in the defining module's parent workflow environment, the
same way :mod:`flyte_migrate._bigquery` registers its templates.
"""

import inspect
import weakref
from typing import Any, Dict, List, Optional, Type, Union, cast

import flyte
import flytekit
from flyte._logging import logger
from flyte.extras import ContainerTask as V2ContainerTask

from flyte_migrate._image import _transform_image_spec_v1_to_v2
from flyte_migrate._pod_template import _transform_pod_template_v1_to_v2
from flyte_migrate._resource import _transform_resource_v1_to_v2
from flyte_migrate._secret import _transform_secret_v1_to_v2
from flyte_migrate._workflow import parent_env_for


def _translate_metadata(metadata: Any) -> Dict[str, Any]:
    """Map the supported v1 ``TaskMetadata`` fields onto v2 TaskTemplate kwargs."""
    if metadata is None:
        return {}
    out: Dict[str, Any] = {}
    if metadata.retries:
        out["retries"] = metadata.retries
    if metadata.timeout:
        out["timeout"] = metadata.timeout
    if metadata.interruptible is not None:
        out["interruptible"] = metadata.interruptible
    if metadata.cache:
        version = getattr(metadata, "cache_version", None)
        out["cache"] = flyte.Cache(
            behavior="override" if version else "auto",
            version_override=version or None,
            serialize=getattr(metadata, "cache_serialize", False),
            ignored_inputs=tuple(getattr(metadata, "cache_ignore_input_vars", ()) or ()),
        )
    return out


def container_task_shim(
    name: str,
    image: Union[str, flytekit.ImageSpec],
    command: List[str],
    inputs: Optional[Dict[str, Type]] = None,
    metadata: Optional[Any] = None,
    arguments: Optional[List[str]] = None,
    outputs: Optional[Dict[str, Type]] = None,
    requests: Optional[flytekit.Resources] = None,
    limits: Optional[flytekit.Resources] = None,
    input_data_dir: Optional[str] = None,
    output_data_dir: Optional[str] = None,
    metadata_format: Any = None,
    io_strategy: Any = None,
    secret_requests: Optional[List[flytekit.Secret]] = None,
    pod_template: Optional[flytekit.PodTemplate] = None,
    pod_template_name: Optional[str] = None,
    local_logs: bool = False,
    resources: Optional[flytekit.Resources] = None,
    **kwargs: Any,
) -> V2ContainerTask:
    """Drop-in replacement for ``flytekit.ContainerTask``."""
    if io_strategy is not None:
        logger.warning("ContainerTask io_strategy is not supported on v2 and ignored")
    if kwargs:
        logger.warning(f"ContainerTask args not supported by flyte-migrate and ignored: {sorted(kwargs)}")

    # ContainerTask is constructed at module scope in user code, so the defining module
    # is the caller's — there is no decorated function to read __module__ off.
    caller = inspect.currentframe().f_back  # type: ignore[union-attr]
    parent_env = parent_env_for(caller.f_globals.get("__name__") if caller else None)

    # v1 metadata_format is an enum (JSON/YAML/PROTO); v2 wants the string.
    fmt = cast(Any, getattr(metadata_format, "name", metadata_format) or "JSON")

    extra: Dict[str, Any] = {
        "resources": _transform_resource_v1_to_v2(requests, limits, resources, None, None),
        "secrets": _transform_secret_v1_to_v2(secret_requests),
        "pod_template": _transform_pod_template_v1_to_v2(pod_template) or pod_template_name,
        **_translate_metadata(metadata),
    }

    tmpl = V2ContainerTask(
        name=f"{parent_env.name}.{name}",
        image=image if isinstance(image, str) else _transform_image_spec_v1_to_v2(image),
        command=command,
        inputs=dict(inputs) if inputs else None,
        arguments=arguments,
        outputs=dict(outputs) if outputs else None,
        input_data_dir=input_data_dir or "/var/inputs",
        output_data_dir=output_data_dir or "/var/outputs",
        metadata_format=fmt,
        local_logs=local_logs,
        short_name=name,
        parent_env=weakref.ref(parent_env),
        parent_env_name=parent_env.name,
        **{k: v for k, v in extra.items() if v is not None},
    )
    parent_env._tasks[tmpl.name] = tmpl
    return tmpl


flytekit.ContainerTask = container_task_shim
