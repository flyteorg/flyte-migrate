"""Tests for control flow patterns: MapShim, LaunchPlan, dynamic, subworkflows."""

import functools
from unittest.mock import MagicMock, patch

import flytekit
from flytekit.models import schedule as _schedule_model

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._launchplan import LaunchPlanTransformer, merge_inputs, schedule_to_trigger
from flyte_migrate._map import MapShim

# ---------------------------------------------------------------------------
# MapShim: concurrency forwarding
# ---------------------------------------------------------------------------


class TestMapShimConcurrency:
    @patch("flyte_migrate._map.flyte.map")
    def test_concurrency_forwarded(self, mock_map):
        """When concurrency is set, it should be forwarded to flyte.map()."""
        mock_map.return_value = [1, 4, 9]
        target = MagicMock()
        shim = MapShim(target, concurrency=5)
        result = shim([1, 2, 3])
        mock_map.assert_called_once_with(target, [1, 2, 3], concurrency=5)
        assert result == [1, 4, 9]

    @patch("flyte_migrate._map.flyte.map")
    def test_concurrency_none_not_forwarded(self, mock_map):
        """When concurrency is None, it should not be passed to flyte.map()."""
        mock_map.return_value = [1, 4, 9]
        target = MagicMock()
        shim = MapShim(target)
        shim([1, 2, 3])
        mock_map.assert_called_once_with(target, [1, 2, 3])

    @patch("flyte_migrate._map.flyte.map")
    def test_concurrency_with_kwargs(self, mock_map):
        """Concurrency should work with keyword argument calling convention."""
        mock_map.return_value = [10, 20]
        target = MagicMock()
        shim = MapShim(target, concurrency=3)
        shim(inputs=[1, 2])
        mock_map.assert_called_once_with(target, [1, 2], concurrency=3)


class TestMapShimMinSuccessRatio:
    def test_accepts_min_success_ratio_without_error(self):
        """min_success_ratio should be accepted without raising."""
        target = MagicMock()
        shim = MapShim(target, min_success_ratio=0.75)
        assert shim.min_success_ratio == 0.75

    def test_accepts_min_successes_without_error(self):
        """min_successes should be accepted without raising."""
        target = MagicMock()
        shim = MapShim(target, min_successes=3)
        assert shim.min_successes == 3

    @patch("flyte_migrate._map.flyte.map")
    def test_min_success_ratio_not_forwarded(self, mock_map):
        """min_success_ratio should not appear in the flyte.map() call."""
        mock_map.return_value = [1]
        target = MagicMock()
        shim = MapShim(target, min_success_ratio=0.5)
        shim([1])
        mock_map.assert_called_once_with(target, [1])


class TestMapShimWithPartialAndConcurrency:
    @patch("flyte_migrate._map.flyte.map")
    def test_partial_with_concurrency(self, mock_map):
        """functools.partial target with concurrency should work together."""
        base_fn = MagicMock()
        partial_fn = functools.partial(base_fn, factor=10)
        mock_map.return_value = [10, 20]
        shim = MapShim(partial_fn, concurrency=4)
        result = shim([1, 2])
        mock_map.assert_called_once_with(partial_fn, [1, 2], concurrency=4)
        assert result == [10, 20]


# ---------------------------------------------------------------------------
# merge_inputs
# ---------------------------------------------------------------------------


class TestMergeInputs:
    def test_both_none(self):
        assert merge_inputs(None, None) == {}

    def test_default_only(self):
        assert merge_inputs({"a": 1}, None) == {"a": 1}

    def test_fixed_only(self):
        assert merge_inputs(None, {"b": 2}) == {"b": 2}

    def test_fixed_overrides_default(self):
        result = merge_inputs({"a": 1, "b": 2}, {"b": 99})
        assert result == {"a": 1, "b": 99}

    def test_disjoint_keys(self):
        result = merge_inputs({"a": 1}, {"b": 2})
        assert result == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# schedule_to_trigger
# ---------------------------------------------------------------------------


class TestScheduleToTrigger:
    def test_none_schedule_returns_none(self):
        result = schedule_to_trigger(name="test", schedule=None)
        assert result is None

    def test_cron_schedule(self):
        schedule = _schedule_model.Schedule(kickoff_time_input_arg="", cron_expression="0 * * * *")
        trigger = schedule_to_trigger(name="cron_trigger", schedule=schedule, auto_activate=True)
        assert trigger is not None
        assert trigger.name == "cron_trigger"
        assert trigger.auto_activate is True

    def test_fixed_rate_schedule(self):
        schedule = _schedule_model.Schedule(
            kickoff_time_input_arg="",
            rate=_schedule_model.Schedule.FixedRate(value=10, unit=_schedule_model.Schedule.FixedRateUnit.MINUTE),
        )
        trigger = schedule_to_trigger(name="rate_trigger", schedule=schedule)
        assert trigger is not None
        assert trigger.name == "rate_trigger"

    def test_with_merged_inputs(self):
        schedule = _schedule_model.Schedule(kickoff_time_input_arg="", cron_expression="0 0 * * *")
        trigger = schedule_to_trigger(
            name="input_trigger",
            schedule=schedule,
            default_inputs={"a": 1},
            fixed_inputs={"b": 2},
        )
        assert trigger is not None
        assert trigger.inputs == {"a": 1, "b": 2}

    def test_overwrite_cache(self):
        schedule = _schedule_model.Schedule(kickoff_time_input_arg="", cron_expression="0 0 * * *")
        trigger = schedule_to_trigger(name="cache_trigger", schedule=schedule, overwrite_cache=True)
        assert trigger is not None
        assert trigger.overwrite_cache is True


# ---------------------------------------------------------------------------
# LaunchPlanTransformer
# ---------------------------------------------------------------------------


class TestLaunchPlanTransformer:
    def test_flytekit_launchplan_is_patched(self):
        """Verify that flytekit.LaunchPlan points to LaunchPlanTransformer."""
        assert flytekit.LaunchPlan is LaunchPlanTransformer

    def test_get_or_create_delegates_to_create(self):
        """get_or_create should call create with same args."""
        with patch.object(LaunchPlanTransformer, "create") as mock_create:
            mock_create.return_value = MagicMock()
            LaunchPlanTransformer.get_or_create(name="test", workflow=MagicMock())
            mock_create.assert_called_once()


# ---------------------------------------------------------------------------
# Example task unit tests
# ---------------------------------------------------------------------------


class TestControlFlowExampleTasks:
    def test_square(self):
        from examples.control_flow_comprehensive import square

        assert square(x=3) == 9
        assert square(x=0) == 0
        assert square(x=-2) == 4

    def test_multiply(self):
        from examples.control_flow_comprehensive import multiply

        assert multiply(x=3, factor=10) == 30
        assert multiply(x=0, factor=5) == 0

    def test_add_offset(self):
        from examples.control_flow_comprehensive import add_offset

        assert add_offset(x=10, offset=1) == 11
        assert add_offset(x=-1, offset=1) == 0

    def test_increment(self):
        from examples.control_flow_comprehensive import increment

        assert increment(x=0) == 1
        assert increment(x=99) == 100

    def test_sum_list(self):
        from examples.control_flow_comprehensive import sum_list

        assert sum_list(values=[1, 2, 3]) == 6
        assert sum_list(values=[]) == 0

    def test_format_result(self):
        from examples.control_flow_comprehensive import format_result

        assert format_result(label="total", value=42) == "total: 42"


class TestLaunchPlanExampleTasks:
    def test_greet(self):
        from examples.launchplan_comprehensive import greet

        assert greet(name="Alice", greeting="Hi") == "Hi, Alice!"
        assert greet(name="Bob") == "Hello, Bob!"

    def test_count_chars(self):
        from examples.launchplan_comprehensive import count_chars

        assert count_chars(text="hello") == 5
        assert count_chars(text="") == 0
