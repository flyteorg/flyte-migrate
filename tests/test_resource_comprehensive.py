"""Comprehensive tests for resource transformation (_resource.py).

Covers all Resource/GPU/accelerator combinations:
- requests-only, limits-only, both together
- resources param alone
- resources + requests mutual exclusion error
- GPU formatting with accelerator
- shared_memory conversion
- ephemeral_storage → disk mapping
"""

from unittest.mock import MagicMock

import flyte
import flytekit
import pytest

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._resource import (
    _format_gpu,
    _format_shared_memory,
    _merge_flytekit_requests_and_limits_to_resources,
    _transform_resource_v1_to_v2,
    set_resource_format,
)


class TestRequestsOnly:
    """Requests-only produces correct v2 Resources with request values."""

    def test_cpu_and_mem(self):
        result = _transform_resource_v1_to_v2(
            requests=flytekit.Resources(cpu="1", mem="512Mi"),
        )
        assert isinstance(result, flyte.Resources)
        assert result.cpu == "1"
        assert result.memory == "512Mi"

    def test_cpu_only(self):
        result = _transform_resource_v1_to_v2(
            requests=flytekit.Resources(cpu="500m"),
        )
        assert isinstance(result, flyte.Resources)
        assert result.cpu == "500m"
        assert result.memory is None

    def test_mem_only(self):
        result = _transform_resource_v1_to_v2(
            requests=flytekit.Resources(mem="2Gi"),
        )
        assert isinstance(result, flyte.Resources)
        assert result.memory == "2Gi"
        assert result.cpu is None


class TestLimitsOnly:
    """Limits-only produces correct v2 Resources with limit values."""

    def test_cpu_and_mem(self):
        result = _transform_resource_v1_to_v2(
            limits=flytekit.Resources(cpu="2", mem="1Gi"),
        )
        assert isinstance(result, flyte.Resources)
        assert result.cpu == "2"
        assert result.memory == "1Gi"

    def test_cpu_only(self):
        result = _transform_resource_v1_to_v2(
            limits=flytekit.Resources(cpu="4"),
        )
        assert isinstance(result, flyte.Resources)
        assert result.cpu == "4"


class TestRequestsAndLimits:
    """Both requests AND limits produces tuples in merged resources."""

    def test_both_cpu_and_mem(self):
        merged = _merge_flytekit_requests_and_limits_to_resources(
            flytekit.Resources(cpu="1", mem="512Mi"),
            flytekit.Resources(cpu="2", mem="1Gi"),
        )
        assert merged.cpu == ("1", "2")
        assert merged.mem == ("512Mi", "1Gi")

    def test_v2_transform_with_both(self):
        result = _transform_resource_v1_to_v2(
            requests=flytekit.Resources(cpu="1", mem="512Mi"),
            limits=flytekit.Resources(cpu="2", mem="1Gi"),
        )
        assert isinstance(result, flyte.Resources)
        # The v2 Resources receives the tuple from the merge
        assert result.cpu == ("1", "2")
        assert result.memory == ("512Mi", "1Gi")

    def test_partial_overlap(self):
        """Requests has cpu, limits has mem — each should pass through individually."""
        merged = _merge_flytekit_requests_and_limits_to_resources(
            flytekit.Resources(cpu="1"),
            flytekit.Resources(mem="2Gi"),
        )
        assert merged.cpu == "1"
        assert merged.mem == "2Gi"


class TestResourcesParamAlone:
    """The `resources` param alone passes through to v2."""

    def test_basic(self):
        result = _transform_resource_v1_to_v2(
            resources=flytekit.Resources(cpu="2", mem="4Gi"),
        )
        assert isinstance(result, flyte.Resources)
        assert result.cpu == "2"
        assert result.memory == "4Gi"

    def test_with_gpu_formatting(self):
        # v2 flyte.Resources validates GPU against known accelerator literals,
        # so we test the format_gpu step separately
        assert _format_gpu(None, "1") == "1"
        assert _format_gpu(None, 2) == "2"


class TestResourcesWithRequestsError:
    """Using resources + requests together raises ValueError."""

    def test_resources_and_requests(self):
        with pytest.raises(ValueError, match="`resource` can not be used together"):
            _transform_resource_v1_to_v2(
                requests=flytekit.Resources(cpu="1"),
                resources=flytekit.Resources(cpu="2"),
            )

    def test_resources_and_limits(self):
        with pytest.raises(ValueError, match="`resource` can not be used together"):
            _transform_resource_v1_to_v2(
                limits=flytekit.Resources(cpu="1"),
                resources=flytekit.Resources(cpu="2"),
            )

    def test_resources_and_both(self):
        with pytest.raises(ValueError, match="`resource` can not be used together"):
            _transform_resource_v1_to_v2(
                requests=flytekit.Resources(cpu="1"),
                limits=flytekit.Resources(cpu="2"),
                resources=flytekit.Resources(cpu="3"),
            )


class TestGpuFormatting:
    """GPU formatting with accelerator."""

    def test_no_gpu_no_accelerator(self):
        assert _format_gpu(None, None) is None

    def test_gpu_count_only(self):
        assert _format_gpu(None, 1) == "1"

    def test_gpu_count_string(self):
        assert _format_gpu(None, "2") == "2"

    def test_accelerator_only(self):
        acc = MagicMock()
        acc.__str__ = lambda self: "nvidia-tesla-t4"
        assert _format_gpu(acc, None) == "nvidia-tesla-t4"

    def test_accelerator_with_count(self):
        acc = MagicMock()
        acc.__str__ = lambda self: "nvidia-tesla-v100"
        assert _format_gpu(acc, 4) == "nvidia-tesla-v100:4"

    def test_accelerator_with_string_count(self):
        acc = MagicMock()
        acc.__str__ = lambda self: "nvidia-a100"
        assert _format_gpu(acc, "2") == "nvidia-a100:2"

    def test_gpu_in_v2_resources_valid_accelerator(self):
        """Use a valid v2 accelerator name to test end-to-end through _transform_resource_v1_to_v2."""
        acc = MagicMock()
        acc.__str__ = lambda self: "T4"
        result = _transform_resource_v1_to_v2(
            resources=flytekit.Resources(cpu="1", gpu="1"),
            accelerator=acc,
        )
        assert isinstance(result, flyte.Resources)
        assert result.gpu == "T4:1"

    def test_gpu_format_count_only(self):
        """GPU count-only formatting (v2 validates the string, so test at format level)."""
        assert _format_gpu(None, 1) == "1"
        assert _format_gpu(None, "1") == "1"


class TestSharedMemoryConversion:
    """shared_memory conversion."""

    def test_none(self):
        assert _format_shared_memory(None) is None

    def test_true_becomes_auto(self):
        assert _format_shared_memory(True) == "auto"

    def test_string_passthrough(self):
        assert _format_shared_memory("2Gi") == "2Gi"

    def test_large_string(self):
        assert _format_shared_memory("16Gi") == "16Gi"

    def test_shared_memory_in_v2_resources_true(self):
        result = _transform_resource_v1_to_v2(
            resources=flytekit.Resources(cpu="1"),
            shared_memory=True,
        )
        assert isinstance(result, flyte.Resources)
        assert result.shm == "auto"

    def test_shared_memory_in_v2_resources_string(self):
        result = _transform_resource_v1_to_v2(
            resources=flytekit.Resources(cpu="1"),
            shared_memory="4Gi",
        )
        assert isinstance(result, flyte.Resources)
        assert result.shm == "4Gi"


class TestEphemeralStorageToDisk:
    """ephemeral_storage → disk mapping."""

    def test_ephemeral_storage_in_requests(self):
        result = _transform_resource_v1_to_v2(
            requests=flytekit.Resources(cpu="1", ephemeral_storage="5Gi"),
        )
        assert isinstance(result, flyte.Resources)
        assert result.disk == "5Gi"

    def test_ephemeral_storage_in_resources(self):
        result = _transform_resource_v1_to_v2(
            resources=flytekit.Resources(cpu="1", ephemeral_storage="10Gi"),
        )
        assert isinstance(result, flyte.Resources)
        assert result.disk == "10Gi"

    def test_ephemeral_storage_requests_and_limits(self):
        result = _transform_resource_v1_to_v2(
            requests=flytekit.Resources(ephemeral_storage="5Gi"),
            limits=flytekit.Resources(ephemeral_storage="10Gi"),
        )
        assert isinstance(result, flyte.Resources)
        assert result.disk == ("5Gi", "10Gi")

    def test_no_ephemeral_storage(self):
        result = _transform_resource_v1_to_v2(
            resources=flytekit.Resources(cpu="1"),
        )
        assert isinstance(result, flyte.Resources)
        assert result.disk is None


class TestSetResourceFormat:
    """set_resource_format helper covers all combos."""

    def test_both(self):
        assert set_resource_format("1", "2") == ("1", "2")

    def test_request_only(self):
        assert set_resource_format("1", None) == "1"

    def test_limit_only(self):
        assert set_resource_format(None, "2") == "2"

    def test_neither(self):
        assert set_resource_format(None, None) is None

    def test_numeric(self):
        assert set_resource_format(1, 2) == (1, 2)


class TestEdgeCases:
    """Edge cases and combined scenarios."""

    def test_empty_requests_and_limits(self):
        """Both empty should produce a valid Resources with all None fields."""
        result = _transform_resource_v1_to_v2(
            requests=flytekit.Resources(),
            limits=flytekit.Resources(),
        )
        assert isinstance(result, flyte.Resources)
        assert result.cpu is None
        assert result.memory is None
        assert result.gpu is None
        assert result.disk is None

    def test_no_args_at_all(self):
        """No arguments should still produce a valid Resources."""
        result = _transform_resource_v1_to_v2()
        assert isinstance(result, flyte.Resources)

    def test_all_fields_together(self):
        """CPU + mem + ephemeral_storage + shared_memory + accelerator."""
        acc = MagicMock()
        acc.__str__ = lambda self: "A100"
        result = _transform_resource_v1_to_v2(
            resources=flytekit.Resources(cpu="4", mem="16Gi", gpu="2", ephemeral_storage="20Gi"),
            accelerator=acc,
            shared_memory="8Gi",
        )
        assert isinstance(result, flyte.Resources)
        assert result.cpu == "4"
        assert result.memory == "16Gi"
        assert result.gpu == "A100:2"
        assert result.disk == "20Gi"
        assert result.shm == "8Gi"
