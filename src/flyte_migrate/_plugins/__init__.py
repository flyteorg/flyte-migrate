from typing import Any, Optional

from flyte_migrate._plugins.dask import _transform_dask_config_v1_to_v2
from flyte_migrate._plugins.ray import _transform_ray_config_v1_to_v2
from flyte_migrate._plugins.spark import _transform_spark_config_v1_to_v2


def _transform_plugin_config_v1_to_v2(v1_config: Optional[Any]) -> Optional[Any]:
    if v1_config is None:
        return None

    cfg = None
    trans = [_transform_spark_config_v1_to_v2, _transform_ray_config_v1_to_v2, _transform_dask_config_v1_to_v2]
    for tran in trans:
        cfg = tran(v1_config)
        if cfg is not None:
            return cfg
    # No config successfully transformed, raise error
    raise NotImplementedError(
        f"Unable to transform plugin config. The provided config type is not supported. "
        f"Supported plugin types: Ray, Spark, Dask. Received config: {v1_config}"
    )
