"""Tests for Spark and Dask plugin transformers."""

from unittest.mock import MagicMock

import flyte
import flytekit
import pytest

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._plugins import _transform_plugin_config_v1_to_v2
from flyte_migrate._plugins.dask import _transform_dask_config_v1_to_v2
from flyte_migrate._plugins.spark import _transform_spark_config_v1_to_v2

# ---------------------------------------------------------------------------
# Spark plugin
# ---------------------------------------------------------------------------


class TestSparkConfigTransform:
    def test_none_returns_none(self):
        assert _transform_spark_config_v1_to_v2(None) is None

    def test_wrong_type_returns_none(self):
        assert _transform_spark_config_v1_to_v2("not a spark config") is None

    def test_basic_spark_conf(self):
        from flytekitplugins.spark import Spark as v1Spark
        from flyteplugins.spark.task import Spark as v2Spark

        v1 = v1Spark(
            spark_conf={
                "spark.driver.memory": "1g",
                "spark.executor.memory": "2g",
                "spark.executor.cores": "2",
                "spark.executor.instances": "3",
            },
        )
        result = _transform_spark_config_v1_to_v2(v1)
        assert isinstance(result, v2Spark)
        assert result.spark_conf == {
            "spark.driver.memory": "1g",
            "spark.executor.memory": "2g",
            "spark.executor.cores": "2",
            "spark.executor.instances": "3",
        }

    def test_hadoop_conf(self):
        from flytekitplugins.spark import Spark as v1Spark
        from flyteplugins.spark.task import Spark as v2Spark

        v1 = v1Spark(
            spark_conf={"spark.driver.memory": "1g"},
            hadoop_conf={
                "fs.s3a.access.key": "key",
                "fs.s3a.secret.key": "secret",
                "fs.s3a.endpoint": "s3.amazonaws.com",
            },
        )
        result = _transform_spark_config_v1_to_v2(v1)
        assert isinstance(result, v2Spark)
        assert result.hadoop_conf == {
            "fs.s3a.access.key": "key",
            "fs.s3a.secret.key": "secret",
            "fs.s3a.endpoint": "s3.amazonaws.com",
        }

    def test_executor_and_applications_path(self):
        from flytekitplugins.spark import Spark as v1Spark
        from flyteplugins.spark.task import Spark as v2Spark

        v1 = v1Spark(
            executor_path="/usr/bin/python3",
            applications_path="/opt/spark/work-dir",
        )
        result = _transform_spark_config_v1_to_v2(v1)
        assert isinstance(result, v2Spark)
        assert result.executor_path == "/usr/bin/python3"
        assert result.applications_path == "/opt/spark/work-dir"

    def test_driver_pod_template(self):
        from flytekitplugins.spark import Spark as v1Spark
        from flyteplugins.spark.task import Spark as v2Spark

        driver_pod = flytekit.PodTemplate(
            primary_container_name="spark-driver",
            labels={"role": "driver"},
            annotations={"note": "driver-ann"},
        )
        v1 = v1Spark(driver_pod=driver_pod)
        result = _transform_spark_config_v1_to_v2(v1)
        assert isinstance(result, v2Spark)
        assert isinstance(result.driver_pod, flyte.PodTemplate)
        assert result.driver_pod.primary_container_name == "spark-driver"
        assert result.driver_pod.labels == {"role": "driver"}
        assert result.driver_pod.annotations == {"note": "driver-ann"}

    def test_executor_pod_template(self):
        from flytekitplugins.spark import Spark as v1Spark
        from flyteplugins.spark.task import Spark as v2Spark

        executor_pod = flytekit.PodTemplate(
            primary_container_name="spark-executor",
            labels={"role": "executor"},
            annotations={"note": "executor-ann"},
        )
        v1 = v1Spark(executor_pod=executor_pod)
        result = _transform_spark_config_v1_to_v2(v1)
        assert isinstance(result, v2Spark)
        assert isinstance(result.executor_pod, flyte.PodTemplate)
        assert result.executor_pod.primary_container_name == "spark-executor"
        assert result.executor_pod.labels == {"role": "executor"}

    def test_both_pod_templates(self):
        from flytekitplugins.spark import Spark as v1Spark

        driver_pod = flytekit.PodTemplate(
            primary_container_name="driver",
            labels={"role": "driver"},
        )
        executor_pod = flytekit.PodTemplate(
            primary_container_name="executor",
            labels={"role": "executor"},
        )
        v1 = v1Spark(
            spark_conf={"spark.executor.instances": "2"},
            driver_pod=driver_pod,
            executor_pod=executor_pod,
        )
        result = _transform_spark_config_v1_to_v2(v1)
        assert result.driver_pod is not None
        assert result.executor_pod is not None
        assert result.driver_pod.labels == {"role": "driver"}
        assert result.executor_pod.labels == {"role": "executor"}

    def test_no_pod_templates_returns_none(self):
        from flytekitplugins.spark import Spark as v1Spark

        v1 = v1Spark(spark_conf={"spark.driver.memory": "1g"})
        result = _transform_spark_config_v1_to_v2(v1)
        assert result.driver_pod is None
        assert result.executor_pod is None

    def test_full_config(self):
        from flytekitplugins.spark import Spark as v1Spark
        from flyteplugins.spark.task import Spark as v2Spark

        driver_pod = flytekit.PodTemplate(primary_container_name="driver")
        v1 = v1Spark(
            spark_conf={"spark.driver.memory": "2g", "spark.executor.memory": "4g"},
            hadoop_conf={"fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem"},
            executor_path="/usr/bin/python3",
            applications_path="/opt/spark/work-dir",
            driver_pod=driver_pod,
        )
        result = _transform_spark_config_v1_to_v2(v1)
        assert isinstance(result, v2Spark)
        assert result.spark_conf["spark.driver.memory"] == "2g"
        assert result.hadoop_conf["fs.s3a.impl"] == "org.apache.hadoop.fs.s3a.S3AFileSystem"
        assert result.executor_path == "/usr/bin/python3"
        assert result.applications_path == "/opt/spark/work-dir"
        assert result.driver_pod is not None
        assert result.executor_pod is None


class TestSparkViaPluginDispatch:
    def test_dispatch_routes_to_spark(self):
        from flytekitplugins.spark import Spark as v1Spark
        from flyteplugins.spark.task import Spark as v2Spark

        v1 = v1Spark(spark_conf={"spark.driver.memory": "1g"})
        result = _transform_plugin_config_v1_to_v2(v1)
        assert isinstance(result, v2Spark)


# ---------------------------------------------------------------------------
# Dask plugin
# ---------------------------------------------------------------------------


class TestDaskConfigTransform:
    def test_none_returns_none(self):
        assert _transform_dask_config_v1_to_v2(None) is None

    def test_wrong_type_returns_none(self):
        assert _transform_dask_config_v1_to_v2("not a dask config") is None

    def test_default_config(self):
        from flytekitplugins.dask import Dask as v1Dask
        from flyteplugins.dask.task import Dask as v2Dask

        v1 = v1Dask()
        result = _transform_dask_config_v1_to_v2(v1)
        assert isinstance(result, v2Dask)

    def test_worker_count(self):
        from flytekitplugins.dask import Dask as v1Dask
        from flytekitplugins.dask import WorkerGroup as v1WG
        from flyteplugins.dask.task import Dask as v2Dask

        v1 = v1Dask(workers=v1WG(number_of_workers=10))
        result = _transform_dask_config_v1_to_v2(v1)
        assert isinstance(result, v2Dask)
        assert result.workers.number_of_workers == 10

    def test_worker_with_image(self):
        from flytekitplugins.dask import Dask as v1Dask
        from flytekitplugins.dask import WorkerGroup as v1WG

        v1 = v1Dask(workers=v1WG(number_of_workers=5, image="ghcr.io/dask/dask:2024.1.0"))
        result = _transform_dask_config_v1_to_v2(v1)
        assert result.workers.image == "ghcr.io/dask/dask:2024.1.0"
        assert result.workers.number_of_workers == 5

    def test_worker_with_resources(self):
        from flytekitplugins.dask import Dask as v1Dask
        from flytekitplugins.dask import WorkerGroup as v1WG

        v1 = v1Dask(
            workers=v1WG(
                number_of_workers=3,
                requests=flytekit.Resources(cpu="2", mem="4Gi"),
                limits=flytekit.Resources(cpu="4", mem="8Gi"),
            ),
        )
        result = _transform_dask_config_v1_to_v2(v1)
        assert result.workers.number_of_workers == 3
        assert isinstance(result.workers.resources, flyte.Resources)

    def test_worker_limits_only(self):
        from flytekitplugins.dask import Dask as v1Dask
        from flytekitplugins.dask import WorkerGroup as v1WG

        v1 = v1Dask(
            workers=v1WG(
                number_of_workers=10,
                limits=flytekit.Resources(cpu="4", mem="10Gi"),
            ),
        )
        result = _transform_dask_config_v1_to_v2(v1)
        assert result.workers.number_of_workers == 10
        assert isinstance(result.workers.resources, flyte.Resources)

    def test_scheduler_with_image(self):
        from flytekitplugins.dask import Dask as v1Dask
        from flytekitplugins.dask import Scheduler as v1Sched

        v1 = v1Dask(scheduler=v1Sched(image="ghcr.io/dask/dask:2024.1.0"))
        result = _transform_dask_config_v1_to_v2(v1)
        assert result.scheduler.image == "ghcr.io/dask/dask:2024.1.0"

    def test_scheduler_with_resources(self):
        from flytekitplugins.dask import Dask as v1Dask
        from flytekitplugins.dask import Scheduler as v1Sched

        v1 = v1Dask(
            scheduler=v1Sched(
                requests=flytekit.Resources(cpu="1", mem="2Gi"),
                limits=flytekit.Resources(cpu="2", mem="4Gi"),
            ),
        )
        result = _transform_dask_config_v1_to_v2(v1)
        assert isinstance(result.scheduler.resources, flyte.Resources)

    def test_full_config(self):
        from flytekitplugins.dask import Dask as v1Dask
        from flytekitplugins.dask import Scheduler as v1Sched
        from flytekitplugins.dask import WorkerGroup as v1WG
        from flyteplugins.dask.task import Dask as v2Dask

        v1 = v1Dask(
            workers=v1WG(
                number_of_workers=8,
                image="ghcr.io/dask/dask:2024.1.0",
                requests=flytekit.Resources(cpu="2", mem="4Gi"),
                limits=flytekit.Resources(cpu="4", mem="8Gi"),
            ),
            scheduler=v1Sched(
                image="ghcr.io/dask/dask:2024.1.0",
                requests=flytekit.Resources(cpu="1", mem="2Gi"),
                limits=flytekit.Resources(cpu="2", mem="4Gi"),
            ),
        )
        result = _transform_dask_config_v1_to_v2(v1)
        assert isinstance(result, v2Dask)
        assert result.workers.number_of_workers == 8
        assert result.workers.image == "ghcr.io/dask/dask:2024.1.0"
        assert isinstance(result.workers.resources, flyte.Resources)
        assert result.scheduler.image == "ghcr.io/dask/dask:2024.1.0"
        assert isinstance(result.scheduler.resources, flyte.Resources)


class TestDaskViaPluginDispatch:
    def test_dispatch_routes_to_dask(self):
        from flytekitplugins.dask import Dask as v1Dask
        from flyteplugins.dask.task import Dask as v2Dask

        v1 = v1Dask()
        result = _transform_plugin_config_v1_to_v2(v1)
        assert isinstance(result, v2Dask)


# ---------------------------------------------------------------------------
# Plugin dispatch edge cases
# ---------------------------------------------------------------------------


class TestPluginDispatch:
    def test_none_returns_none(self):
        assert _transform_plugin_config_v1_to_v2(None) is None

    def test_unsupported_type_raises(self):
        with pytest.raises(NotImplementedError, match="not supported"):
            _transform_plugin_config_v1_to_v2(MagicMock(__class__=type("UnknownPlugin", (), {})))
