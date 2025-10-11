from typing import Any, Optional

from flyte_migrate._plugins.spark import _transform_spark_config_v1_to_v2


def _transform_plugin_config_v1_to_v2(v1_config: Optional[Any]) -> Optional[Any]:
    cfg = None
    trans = [_transform_spark_config_v1_to_v2]
    for tran in trans:
        cfg = tran(v1_config)
        if cfg is not None:
            return cfg
    return cfg
