"""
Comprehensive data types example exercising all common v1 flytekit type patterns
through the flyte-migrate shim:

- Basic types: int, float, str, bool
- Generic collections: List[int], Dict[str, float]
- Optional types
- @dataclass as task input/output
- Enum types
- datetime.datetime, datetime.timedelta
- FlyteFile
- Multiple return values
- Default parameter values
- typing.Annotated
"""

import flyte_migrate  # noqa: F401, I001
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Dict, List, Optional, Tuple

from flytekit import ImageSpec, task, workflow
from flytekit.types.file import FlyteFile

image = ImageSpec(packages=["pandas"])


# ---------------------------------------------------------------------------
# Dataclass for structured task output
#
# NOTE: v1 allows a NamedTuple here, but v2 flattens it into separate output
# variables and hands the caller a plain tuple, so `stats.total` in the workflow
# below raises "'tuple' object has no attribute 'total'". A dataclass survives
# the round trip with attribute access intact.
# ---------------------------------------------------------------------------


@dataclass
class StatsResult:
    mean: float
    total: int
    label: str


# ---------------------------------------------------------------------------
# Dataclass for structured I/O
# ---------------------------------------------------------------------------


@dataclass
class UserProfile:
    name: str
    age: int
    score: float
    active: bool = True


@dataclass
class ProcessedProfile:
    original_name: str
    greeting: str
    adjusted_score: float


# ---------------------------------------------------------------------------
# Enum for categorical inputs
# ---------------------------------------------------------------------------


class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@task(container_image=image)
def compute_stats(values: List[int], label: str) -> StatsResult:
    """Task returning a structured dataclass output."""
    total = sum(values)
    mean = total / len(values) if values else 0.0
    return StatsResult(mean=mean, total=total, label=label)


@task(container_image=image)
def process_profile(profile: UserProfile) -> ProcessedProfile:
    """Task accepting and returning dataclass objects."""
    greeting = f"Hello, {profile.name}! You are {profile.age} years old."
    adjusted = profile.score * (1.5 if profile.active else 0.5)
    return ProcessedProfile(
        original_name=profile.name,
        greeting=greeting,
        adjusted_score=adjusted,
    )


@task(container_image=image)
def task_with_optional(x: int, multiplier: Optional[int] = None, tag: str = "default") -> str:
    """Task with Optional parameter and default values."""
    result = x * (multiplier if multiplier is not None else 1)
    return f"{tag}: {result}"


@task(container_image=image)
def list_to_dict(values: List[int]) -> Dict[str, float]:
    """Task with List input and Dict output."""
    return {
        "sum": float(sum(values)),
        "count": float(len(values)),
        "mean": sum(values) / len(values) if values else 0.0,
    }


@task(container_image=image)
def format_datetime(dt: datetime) -> str:
    """Task with datetime input."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@task(container_image=image)
def process_timedelta(duration: timedelta) -> float:
    """Task with timedelta input."""
    return duration.total_seconds()


@task(container_image=image)
def create_temp_file(content: str) -> FlyteFile:
    """Task that creates and returns a FlyteFile."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        return FlyteFile(path=f.name)


@task(container_image=image)
def read_file(ff: FlyteFile) -> str:
    """Task that reads a FlyteFile."""
    with open(ff, "r") as f:
        return f.read()


@task(container_image=image)
def multiple_returns(x: int, y: int) -> Tuple[int, float, str]:
    """Task with multiple return values."""
    return x + y, (x + y) / 2.0, f"sum={x + y}"


@task(container_image=image)
def basic_types_task(i: int, f: float, s: str, b: bool) -> str:
    """Task with all basic types."""
    return f"int={i}, float={f}, str={s}, bool={b}"


@task(container_image=image)
def priority_task(p: Priority) -> str:
    """Task with Enum input."""
    return f"Priority is: {p.value}"


@task(container_image=image)
def annotated_task(x: Annotated[int, "a positive integer"]) -> Annotated[str, "result description"]:
    """Task with Annotated types."""
    return f"Got annotated value: {x}"


# ---------------------------------------------------------------------------
# Workflow connecting all tasks
# ---------------------------------------------------------------------------


@workflow
def datatypes_wf(
    values: List[int] = [1, 2, 3, 4, 5],
    name: str = "Alice",
    age: int = 30,
    score: float = 85.5,
    dt: datetime = datetime(2025, 1, 15, 10, 30, 0),
    duration: timedelta = timedelta(hours=2, minutes=30),
    priority: Priority = Priority.MEDIUM,
) -> str:
    """Workflow exercising all data type patterns."""
    # Basic types
    basics = basic_types_task(i=age, f=score, s=name, b=True)

    # Structured dataclass output
    stats = compute_stats(values=values, label=name)

    # Dataclass I/O
    profile = UserProfile(name=name, age=age, score=score, active=True)
    _processed = process_profile(profile=profile)

    # Optional and defaults
    _opt_result = task_with_optional(x=stats.total, multiplier=2, tag="doubled")

    # List -> Dict
    _dict_result = list_to_dict(values=values)

    # datetime
    _dt_str = format_datetime(dt=dt)

    # timedelta
    _td_secs = process_timedelta(duration=duration)

    # FlyteFile
    file_out = create_temp_file(content="hello flyte-migrate datatypes")
    _file_content = read_file(ff=file_out)

    # Multiple returns
    _sum, _avg, _sum_str = multiple_returns(x=stats.total, y=age)

    # Enum
    _prio_str = priority_task(p=priority)

    # Annotated
    _ann_result = annotated_task(x=age)

    # Return a summary string from one of the tasks
    return basics


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(
        datatypes_wf,
        values=[1, 2, 3, 4, 5],
        name="Alice",
        age=30,
        score=85.5,
        dt=datetime(2025, 1, 15, 10, 30, 0),
        duration=timedelta(hours=2, minutes=30),
        priority=Priority.MEDIUM,
    )
    print(run.name)
    print(run.url)
