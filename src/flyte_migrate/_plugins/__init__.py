from typing import Any, Optional

from flyte_migrate._plugins.dask import _transform_dask_config_v1_to_v2
from flyte_migrate._plugins.pytorch import _transform_pytorch_config_v1_to_v2
from flyte_migrate._plugins.ray import _transform_ray_config_v1_to_v2
from flyte_migrate._plugins.spark import _transform_spark_config_v1_to_v2

# Map config type names to their transformer functions
transformer_map = {
    "Spark": _transform_spark_config_v1_to_v2,
    "RayJobConfig": _transform_ray_config_v1_to_v2,
    "Dask": _transform_dask_config_v1_to_v2,
    "Elastic": _transform_pytorch_config_v1_to_v2,
}


def _transform_plugin_config_v1_to_v2(v1_config: Optional[Any]) -> Optional[Any]:
    if v1_config is None:
        return None

    # Get the config type name
    config_type = v1_config.__class__.__name__

    # Get the appropriate transformer. Raise error if no plugin found.
    transformer = transformer_map.get(config_type)
    if transformer is None:
        raise NotImplementedError(
            f"Unable to transform plugin config. The provided config type '{config_type}' is not supported. "
            f"Supported plugin types: {', '.join(transformer_map.keys())}. Received config: {v1_config}"
        )

    # Call the transformer for this config type
    return transformer(v1_config)
