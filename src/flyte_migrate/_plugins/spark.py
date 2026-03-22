"""Spark plugin transformer: v1 ``flytekitplugins.spark.Spark`` -> v2 ``flyteplugins.spark.task.Spark``."""

from typing import Any, Optional

from flyte_migrate._pod_template import _transform_pod_template_v1_to_v2


def _transform_spark_config_v1_to_v2(v1_config: Optional[Any]) -> Optional[Any]:
    """Convert a v1 Spark config to its v2 equivalent.

    Translates Spark/Hadoop configuration, executor/driver paths, and pod
    templates for the driver and executor.

    Returns:
        A v2 ``Spark`` config, or ``None`` if *v1_config* is not the expected type.

    Raises:
        ModuleNotFoundError: If the required Spark plugin packages are missing.
    """
    try:
        from flytekitplugins.spark import Spark as v1Spark
        from flyteplugins.spark.task import Spark as v2Spark
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(f"Spark plugin is not installed. Please ensure that {e.name} is installed.") from e

    if not isinstance(v1_config, v1Spark):
        return None

    return v2Spark(
        spark_conf=v1_config.spark_conf,
        hadoop_conf=v1_config.hadoop_conf,
        executor_path=v1_config.executor_path,
        applications_path=v1_config.applications_path,
        driver_pod=_transform_pod_template_v1_to_v2(v1_config.driver_pod),
        executor_pod=_transform_pod_template_v1_to_v2(v1_config.executor_pod),
    )
