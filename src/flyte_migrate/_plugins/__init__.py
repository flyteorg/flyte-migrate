"""Plugin configuration transformers for v1-to-v2 migration.

Each plugin module provides a transformer function that converts a v1 plugin
configuration object into its v2 equivalent. The registry pattern used here
allows new plugins to be added without modifying the dispatch logic.

Supported plugins:
    - Spark (``flytekitplugins.spark``)
    - Ray (``flytekitplugins.ray``)
    - Dask (``flytekitplugins.dask``)
    - PyTorch / Elastic (``flytekitplugins.kfpytorch``)
"""

from typing import Any, Callable, Dict, Optional

from flyte_migrate._plugins.dask import _transform_dask_config_v1_to_v2
from flyte_migrate._plugins.pytorch import _transform_pytorch_config_v1_to_v2
from flyte_migrate._plugins.ray import _transform_ray_config_v1_to_v2
from flyte_migrate._plugins.spark import _transform_spark_config_v1_to_v2

# Maps a v1 config class name (e.g. ``"Spark"``) to its transformer function.
_transformer_registry: Dict[str, Callable[[Any], Any]] = {}


def register_plugin(config_class_name: str, transformer: Callable[[Any], Any]) -> None:
    """Register a transformer for a v1 plugin config type.

    Args:
        config_class_name: The ``__name__`` of the v1 configuration class
            (e.g. ``"Spark"``, ``"RayJobConfig"``).
        transformer: A callable that accepts a v1 config instance and returns
            the corresponding v2 config, or ``None`` if the input is not the
            expected type.
    """
    _transformer_registry[config_class_name] = transformer


# Register built-in plugins
register_plugin("Spark", _transform_spark_config_v1_to_v2)
register_plugin("RayJobConfig", _transform_ray_config_v1_to_v2)
register_plugin("Dask", _transform_dask_config_v1_to_v2)
register_plugin("Elastic", _transform_pytorch_config_v1_to_v2)


def _transform_plugin_config_v1_to_v2(v1_config: Optional[Any]) -> Optional[Any]:
    """Transform a v1 plugin configuration into its v2 equivalent.

    Looks up the transformer by the v1 config object's class name and delegates
    the conversion. Returns ``None`` when *v1_config* is ``None``.

    Raises:
        NotImplementedError: If no transformer is registered for the config type.
    """
    if v1_config is None:
        return None

    config_type = v1_config.__class__.__name__

    transformer = _transformer_registry.get(config_type)
    if transformer is None:
        raise NotImplementedError(
            f"Unable to transform plugin config. The provided config type '{config_type}' is not supported. "
            f"Supported plugin types: {', '.join(_transformer_registry.keys())}. Received config: {v1_config}"
        )

    return transformer(v1_config)
