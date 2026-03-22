import flyte_migrate  # noqa: F401, I001
import datetime
import logging
import random
from operator import add

import flytekit
from flytekit import ImageSpec, Resources, task, workflow
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
    print("spark version", session.version)  # spark version 3.5.3
    print("Starting Spark with Partitions: {}".format(partitions))

    n = 1 * partitions
    sess = flytekit.current_context().spark_session
    count = sess.sparkContext.parallelize(range(1, n + 1), partitions).map(f).reduce(add)

    pi_val = 4.0 * count / n
    return pi_val


def f(_):
    x = random.random() * 2 - 1
    y = random.random() * 2 - 1
    return 1 if x**2 + y**2 <= 1 else 0


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
    return pi


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(my_spark)
    print(run.name)
    print(run.url)
