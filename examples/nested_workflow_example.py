import flyte_migrate  # noqa: F401, I001
import logging
from typing import Tuple

from flytekit import task, workflow


@task
def fetch_data(source: str) -> list[float]:
    """Simulate fetching data from a source."""
    if source == "sensor_a":
        return [1.0, 2.5, 3.7, 4.2, 5.1]
    elif source == "sensor_b":
        return [10.0, 20.0, 30.0, 40.0, 50.0]
    return [0.0]


@task
def compute_mean(data: list[float]) -> float:
    """Compute the mean of a list of numbers."""
    return sum(data) / len(data) if data else 0.0


@task
def compute_std(data: list[float]) -> float:
    """Compute the standard deviation of a list of numbers."""
    if not data:
        return 0.0
    mean = sum(data) / len(data)
    variance = sum((x - mean) ** 2 for x in data) / len(data)
    return variance**0.5


@task
def combine_stats(mean_a: float, std_a: float, mean_b: float, std_b: float) -> str:
    """Combine statistics from two sources into a report."""
    return (
        f"Sensor A: mean={mean_a:.2f}, std={std_a:.2f} | "
        f"Sensor B: mean={mean_b:.2f}, std={std_b:.2f}"
    )


@workflow
def analyze_sensor(source: str) -> Tuple[float, float]:
    """
    Sub-workflow that analyzes data from a single sensor.
    Returns (mean, std) as a tuple.
    """
    data = fetch_data(source=source)
    mean = compute_mean(data=data)
    std = compute_std(data=data)
    return mean, std


@workflow
def multi_sensor_wf() -> str:
    """
    Demonstrates nested workflows (workflow calling workflow).

    The parent workflow calls analyze_sensor twice (once per sensor)
    and combines the results into a single report.
    """
    mean_a, std_a = analyze_sensor(source="sensor_a")
    mean_b, std_b = analyze_sensor(source="sensor_b")
    report = combine_stats(mean_a=mean_a, std_a=std_a, mean_b=mean_b, std_b=std_b)
    return report


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(
        multi_sensor_wf
    )
    print(run.name)
    print(run.url)
