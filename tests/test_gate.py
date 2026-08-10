"""Tests for the v1 gate-node shims (approve, wait_for_input, sleep)."""

from datetime import timedelta
from unittest.mock import patch

import flytekit
import pytest
from flytekit.exceptions.user import FlyteDisapprovalException

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._gate import approve_shim, sleep_shim, wait_for_input_shim


class TestPatching:
    def test_flytekit_gates_are_patched(self):
        assert flytekit.approve is approve_shim
        assert flytekit.sleep is sleep_shim
        assert flytekit.wait_for_input is wait_for_input_shim


class TestWaitForInput:
    @patch("flyte_migrate._gate.flyte.new_condition")
    def test_returns_condition_result(self, mock_cond):
        mock_cond.return_value.wait.return_value = 42
        assert wait_for_input_shim("threshold", timeout=timedelta(hours=1), expected_type=int) == 42
        mock_cond.assert_called_once_with(
            "threshold", prompt="Provide input 'threshold'", data_type=int, timeout=timedelta(hours=1)
        )


class TestApprove:
    @patch("flyte_migrate._gate.flyte.new_condition")
    def test_approved_returns_upstream_item(self, mock_cond):
        mock_cond.return_value.wait.return_value = True
        assert approve_shim("model-v3", "deploy-gate", timeout=timedelta(hours=1)) == "model-v3"
        assert mock_cond.call_args.kwargs["data_type"] is bool

    @patch("flyte_migrate._gate.flyte.new_condition")
    def test_disapproved_raises_v1_exception(self, mock_cond):
        mock_cond.return_value.wait.return_value = False
        with pytest.raises(FlyteDisapprovalException, match="deploy-gate"):
            approve_shim("model-v3", "deploy-gate", timeout=timedelta(hours=1))


class TestSleep:
    def test_timedelta_and_numeric_durations(self):
        sleep_shim(timedelta(seconds=0))
        sleep_shim(0)
