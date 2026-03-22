"""Tests for the MapShim (_map.py) and map_task_advanced example patterns."""

import functools
from unittest.mock import MagicMock, patch

import flytekit

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._map import MapShim


class TestMapShimInit:
    def test_default_init(self):
        target = MagicMock()
        shim = MapShim(target)
        assert shim.target is target
        assert shim.concurrency is None
        assert shim.min_successes is None
        assert shim.min_success_ratio is None

    def test_init_with_params(self):
        target = MagicMock()
        shim = MapShim(target, concurrency=5, min_successes=3, min_success_ratio=0.8)
        assert shim.concurrency == 5
        assert shim.min_successes == 3
        assert shim.min_success_ratio == 0.8

    def test_init_with_extra_kwargs(self):
        target = MagicMock()
        shim = MapShim(target, some_extra="value")
        assert shim.kwargs == {"some_extra": "value"}


class TestMapShimCall:
    @patch("flyte_migrate._map.flyte.map")
    def test_call_with_positional_args(self, mock_map):
        mock_map.return_value = [1, 4, 9]
        target = MagicMock()
        shim = MapShim(target)
        result = shim([1, 2, 3])
        mock_map.assert_called_once_with(target, [1, 2, 3])
        assert result == [1, 4, 9]

    @patch("flyte_migrate._map.flyte.map")
    def test_call_with_kwargs(self, mock_map):
        mock_map.return_value = [10, 20, 30]
        target = MagicMock()
        shim = MapShim(target)
        result = shim(inputs=[1, 2, 3])
        mock_map.assert_called_once_with(target, [1, 2, 3])
        assert result == [10, 20, 30]

    @patch("flyte_migrate._map.flyte.map")
    def test_call_returns_list(self, mock_map):
        """Ensure the result is always a list, not a generator or other iterable."""
        mock_map.return_value = iter([1, 2, 3])
        target = MagicMock()
        shim = MapShim(target)
        result = shim([1, 2, 3])
        assert isinstance(result, list)
        assert result == [1, 2, 3]


class TestMapTaskPatch:
    def test_flytekit_map_task_is_patched(self):
        """Verify that flytekit.map_task points to MapShim after import."""
        assert flytekit.map_task is MapShim


class TestMapShimWithPartial:
    @patch("flyte_migrate._map.flyte.map")
    def test_partial_target(self, mock_map):
        """MapShim should accept a functools.partial as the target."""
        base_fn = MagicMock()
        partial_fn = functools.partial(base_fn, factor=10)
        mock_map.return_value = [10, 20, 30]
        shim = MapShim(partial_fn)
        result = shim([1, 2, 3])
        mock_map.assert_called_once_with(partial_fn, [1, 2, 3])
        assert result == [10, 20, 30]
