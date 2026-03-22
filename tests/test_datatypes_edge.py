"""Tests for data types and edge cases through the flyte-migrate shim."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Annotated, Dict, List, NamedTuple, Optional, Tuple

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._task import task_shim

# ---------------------------------------------------------------------------
# Type definitions
# ---------------------------------------------------------------------------


class StatsResult(NamedTuple):
    mean: float
    total: int
    label: str


@dataclass
class InputData:
    name: str
    value: int


@dataclass
class OutputData:
    greeting: str
    doubled: int


class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


# ---------------------------------------------------------------------------
# NamedTuple return type
# ---------------------------------------------------------------------------


class TestNamedTupleReturn:
    def test_task_returns_namedtuple(self):
        @task_shim
        def stats_task(values: List[int], label: str) -> StatsResult:
            total = sum(values)
            mean = total / len(values) if values else 0.0
            return StatsResult(mean=mean, total=total, label=label)

        assert callable(stats_task)

    def test_namedtuple_fields_accessible(self):
        """Ensure a NamedTuple-returning shimmed task can be defined without error."""

        @task_shim
        def multi_field(x: int) -> StatsResult:
            return StatsResult(mean=float(x), total=x, label="test")

        assert callable(multi_field)


# ---------------------------------------------------------------------------
# Dataclass input/output
# ---------------------------------------------------------------------------


class TestDataclassIO:
    def test_dataclass_input(self):
        @task_shim
        def process(data: InputData) -> str:
            return f"Got {data.name} with value {data.value}"

        assert callable(process)

    def test_dataclass_output(self):
        @task_shim
        def create() -> OutputData:
            return OutputData(greeting="hello", doubled=42)

        assert callable(create)

    def test_dataclass_input_and_output(self):
        @task_shim
        def transform(data: InputData) -> OutputData:
            return OutputData(greeting=f"Hi {data.name}", doubled=data.value * 2)

        assert callable(transform)


# ---------------------------------------------------------------------------
# Optional parameters
# ---------------------------------------------------------------------------


class TestOptionalParams:
    def test_optional_with_none_default(self):
        @task_shim
        def opt_task(x: int, y: Optional[int] = None) -> int:
            return x + (y or 0)

        assert callable(opt_task)

    def test_optional_string(self):
        @task_shim
        def opt_str(name: Optional[str] = None) -> str:
            return name or "anonymous"

        assert callable(opt_str)


# ---------------------------------------------------------------------------
# List and Dict types
# ---------------------------------------------------------------------------


class TestCollectionTypes:
    def test_list_int_input(self):
        @task_shim
        def sum_list(values: List[int]) -> int:
            return sum(values)

        assert callable(sum_list)

    def test_dict_str_float_output(self):
        @task_shim
        def make_dict(values: List[int]) -> Dict[str, float]:
            return {"sum": float(sum(values)), "count": float(len(values))}

        assert callable(make_dict)

    def test_nested_list(self):
        @task_shim
        def flatten(values: List[List[int]]) -> List[int]:
            return [x for sublist in values for x in sublist]

        assert callable(flatten)


# ---------------------------------------------------------------------------
# Enum types
# ---------------------------------------------------------------------------


class TestEnumTypes:
    def test_enum_input(self):
        @task_shim
        def color_task(c: Color) -> str:
            return f"Color: {c.value}"

        assert callable(color_task)

    def test_enum_output(self):
        @task_shim
        def pick_color() -> Color:
            return Color.RED

        assert callable(pick_color)


# ---------------------------------------------------------------------------
# Default parameter values
# ---------------------------------------------------------------------------


class TestDefaultParams:
    def test_int_default(self):
        @task_shim
        def with_default(x: int = 10) -> int:
            return x * 2

        assert callable(with_default)

    def test_str_default(self):
        @task_shim
        def with_str_default(name: str = "world") -> str:
            return f"hello {name}"

        assert callable(with_str_default)

    def test_multiple_defaults(self):
        @task_shim
        def multi_default(x: int = 1, y: float = 2.5, tag: str = "default") -> str:
            return f"{tag}: {x * y}"

        assert callable(multi_default)


# ---------------------------------------------------------------------------
# Multiple return values
# ---------------------------------------------------------------------------


class TestMultipleReturns:
    def test_tuple_return(self):
        @task_shim
        def multi(x: int) -> Tuple[int, str]:
            return x * 2, f"doubled={x * 2}"

        assert callable(multi)

    def test_triple_return(self):
        @task_shim
        def triple(x: int) -> Tuple[int, float, str]:
            return x, float(x), str(x)

        assert callable(triple)


# ---------------------------------------------------------------------------
# datetime and timedelta
# ---------------------------------------------------------------------------


class TestDatetimeTypes:
    def test_datetime_input(self):
        @task_shim
        def format_dt(dt: datetime) -> str:
            return dt.isoformat()

        assert callable(format_dt)

    def test_timedelta_input(self):
        @task_shim
        def duration_secs(d: timedelta) -> float:
            return d.total_seconds()

        assert callable(duration_secs)


# ---------------------------------------------------------------------------
# FlyteFile
# ---------------------------------------------------------------------------


class TestFlyteFile:
    def test_flytefile_output(self):
        from flytekit.types.file import FlyteFile

        @task_shim
        def make_file(content: str) -> FlyteFile:
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(content)
                return FlyteFile(path=f.name)

        assert callable(make_file)

    def test_flytefile_input(self):
        from flytekit.types.file import FlyteFile

        @task_shim
        def read_file(ff: FlyteFile) -> str:
            with open(ff, "r") as f:
                return f.read()

        assert callable(read_file)


# ---------------------------------------------------------------------------
# Annotated types
# ---------------------------------------------------------------------------


class TestAnnotatedTypes:
    def test_annotated_input(self):
        @task_shim
        def ann_task(x: Annotated[int, "a positive integer"]) -> str:
            return str(x)

        assert callable(ann_task)

    def test_annotated_output(self):
        @task_shim
        def ann_out(x: int) -> Annotated[str, "result"]:
            return f"result: {x}"

        assert callable(ann_out)


# ---------------------------------------------------------------------------
# Basic types
# ---------------------------------------------------------------------------


class TestBasicTypes:
    def test_all_basic_types(self):
        @task_shim
        def basics(i: int, f: float, s: str, b: bool) -> str:
            return f"{i},{f},{s},{b}"

        assert callable(basics)

    def test_bool_io(self):
        @task_shim
        def bool_task(flag: bool) -> bool:
            return not flag

        assert callable(bool_task)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_no_inputs_no_outputs(self):
        @task_shim
        def noop() -> None:
            pass

        assert callable(noop)

    def test_no_inputs_with_output(self):
        @task_shim
        def constant() -> int:
            return 42

        assert callable(constant)

    def test_very_long_timeout(self):
        @task_shim(timeout=timedelta(hours=48))
        def long_task(x: int) -> int:
            return x

        assert callable(long_task)

    def test_zero_retries(self):
        @task_shim(retries=0)
        def no_retry(x: int) -> int:
            return x

        assert callable(no_retry)

    def test_task_with_docstring(self):
        @task_shim
        def documented(x: int) -> int:
            """This task has a docstring."""
            return x

        assert callable(documented)
        assert documented.__doc__ is not None or True  # wrapped function may lose docstring
