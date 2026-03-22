"""Tests for examples/subworkflow_dynamic.py task functions."""

import os

import flyte_migrate  # noqa: F401 — triggers patching

os.environ["MY_VAR"] = "my_value"

from examples.subworkflow_dynamic import (
    SummaryResult,
    add_one,
    build_metadata,
    compute_summary,
    maybe_double,
    multiply,
    sum_list,
)


class TestAddOne:
    def test_basic(self):
        assert add_one(x=0) == 1

    def test_negative(self):
        assert add_one(x=-1) == 0

    def test_large(self):
        assert add_one(x=999) == 1000


class TestMultiply:
    def test_basic(self):
        assert multiply(x=3, factor=2.0) == 6.0

    def test_zero_factor(self):
        assert multiply(x=5, factor=0.0) == 0.0

    def test_fractional(self):
        assert multiply(x=4, factor=0.5) == 2.0


class TestSumList:
    def test_basic(self):
        assert sum_list(values=[1, 2, 3]) == 6

    def test_empty(self):
        assert sum_list(values=[]) == 0

    def test_single(self):
        assert sum_list(values=[42]) == 42


class TestBuildMetadata:
    def test_basic(self):
        result = build_metadata(name="test", count=10)
        assert result == {"name": "test", "count": "10", "status": "completed"}

    def test_zero_count(self):
        result = build_metadata(name="zero", count=0)
        assert result["count"] == "0"


class TestMaybeDouble:
    def test_no_double(self):
        assert maybe_double(x=5) == 5

    def test_with_none(self):
        assert maybe_double(x=5, should_double=None) == 5

    def test_with_zero(self):
        assert maybe_double(x=5, should_double=0) == 5

    def test_double(self):
        assert maybe_double(x=5, should_double=1) == 10

    def test_double_negative(self):
        assert maybe_double(x=-3, should_double=1) == -6


class TestComputeSummary:
    def test_basic(self):
        result = compute_summary(values=[2, 4, 6], label="test")
        assert isinstance(result, SummaryResult)
        assert result.total == 12
        assert result.average == 4.0
        assert result.label == "test"

    def test_single_value(self):
        result = compute_summary(values=[7], label="single")
        assert result.total == 7
        assert result.average == 7.0

    def test_named_tuple_unpacking(self):
        total, average, label = compute_summary(values=[10, 20], label="unpack")
        assert total == 30
        assert average == 15.0
        assert label == "unpack"
