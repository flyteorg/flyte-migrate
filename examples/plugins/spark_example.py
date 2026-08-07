import flyte_migrate  # noqa: F401, I001
import datetime
import logging
from operator import add

import flytekit
from flytekit import ImageSpec, PodTemplate, Resources, task, workflow
from flytekitplugins.spark import Spark


custom_image = ImageSpec(
    base_image="apache/spark-py:v3.4.0", python_version="3.10", packages=["flytekitplugins-spark==1.16.3", "pyspark"]
)


@task(
    task_config=Spark(
        spark_conf={
            "spark.driver.memory": "1000M",
            "spark.executor.memory": "1000M",
            "spark.executor.cores": "1",
            "spark.executor.instances": "2",
            "spark.driver.cores": "1",
            "spark.kubernetes.file.upload.path": "/opt/spark/work-dir",
            "spark.jars": "https://storage.googleapis.com/hadoop-lib/gcs/gcs-connector-hadoop3-latest.jar,https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.2.2/hadoop-aws-3.2.2.jar,https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar",
        },
    ),
    limits=Resources(mem="2000M"),
    container_image=custom_image,
)
def hello_spark(partitions: int = 3) -> float:
    session = flytekit.current_context().spark_session
    print("spark version", session.version)
    print("Starting Spark with Partitions: {}".format(partitions))

    # Define f inside the task so Spark executors don't need to import the
    # top-level module (which requires flyte_migrate, not available remotely).
    def f(_):
        import random

        x = random.random() * 2 - 1
        y = random.random() * 2 - 1
        return 1 if x**2 + y**2 <= 1 else 0

    n = 1 * partitions
    count = session.sparkContext.parallelize(range(1, n + 1), partitions).map(f).reduce(add)

    pi_val = 4.0 * count / n
    return pi_val


@task(
    task_config=Spark(
        spark_conf={
            "spark.driver.memory": "2g",
            "spark.executor.memory": "2g",
            "spark.executor.cores": "2",
            "spark.executor.instances": "3",
            "spark.sql.shuffle.partitions": "200",
            "spark.sql.adaptive.enabled": "true",
            "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
        },
        hadoop_conf={
            "fs.s3a.access.key": "MY_ACCESS_KEY",
            "fs.s3a.secret.key": "MY_SECRET_KEY",
            "fs.s3a.endpoint": "s3.amazonaws.com",
            "fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
        },
    ),
    limits=Resources(mem="4Gi"),
    container_image=custom_image,
)
def spark_with_hadoop_conf(size: int = 100) -> float:
    """Spark task demonstrating hadoop_conf for S3 access."""
    session = flytekit.current_context().spark_session

    # Define helper inside the task to avoid pickling module-level imports
    def compute_sum(x):
        return x * x

    rdd = session.sparkContext.parallelize(range(size))
    total = rdd.map(compute_sum).reduce(lambda a, b: a + b)
    return float(total)


@task(
    task_config=Spark(
        spark_conf={
            "spark.driver.memory": "1g",
            "spark.executor.memory": "1g",
            "spark.executor.instances": "1",
        },
        driver_pod=PodTemplate(
            primary_container_name="spark-driver",
            labels={"role": "driver", "app": "flyte-spark"},
            annotations={"driver-note": "custom-driver-pod"},
        ),
        executor_pod=PodTemplate(
            primary_container_name="spark-executor",
            labels={"role": "executor", "app": "flyte-spark"},
            annotations={"executor-note": "custom-executor-pod"},
        ),
    ),
    limits=Resources(mem="2Gi"),
    container_image=custom_image,
)
def spark_with_pod_templates(n: int = 10) -> int:
    """Spark task demonstrating driver_pod and executor_pod templates."""
    session = flytekit.current_context().spark_session

    def identity(x):
        return x

    total = session.sparkContext.parallelize(range(n)).map(identity).reduce(lambda a, b: a + b)
    return total


@task(
    cache_version="2",
    container_image=custom_image,
)
def print_every_time(value_to_print: float, date_triggered: datetime.datetime) -> int:
    print("My printed value: {} @ {}".format(value_to_print, date_triggered))
    return 1


@workflow
def my_spark(triggered_date: datetime.datetime = datetime.datetime.now()) -> float:
    """
    Using the workflow is still as any other workflow. As image is a property of the task, the workflow does not care
    about how the image is configured.
    """
    pi = hello_spark(partitions=1)
    print_every_time(value_to_print=pi, date_triggered=triggered_date)
    # spark_with_hadoop_conf(size=50)
    # spark_with_pod_templates(n=10)
    return pi


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(my_spark)
    print(run.name)
    print(run.url)
