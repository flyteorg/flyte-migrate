"""Tests for the transformation utility modules (_resource.py, _image.py, _secret.py, _pod_template.py)."""

from unittest.mock import MagicMock

import flyte
import flytekit
import pytest

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._image import (
    _PACKAGE_V1_TO_V2,
    _build_pip_secret_mounts,
    _extract_attributes,
    _parse_platform,
    _parse_python_version,
    _pin_to_flyte_version,
    _translate_pip_packages,
)
from flyte_migrate._pod_template import _transform_pod_template_v1_to_v2
from flyte_migrate._resource import (
    _format_gpu,
    _format_shared_memory,
    _merge_flytekit_requests_and_limits_to_resources,
    _transform_resource_v1_to_v2,
    set_resource_format,
)
from flyte_migrate._secret import _convert_single_secret, _transform_secret_v1_to_v2

# ---------------------------------------------------------------------------
# _resource.py
# ---------------------------------------------------------------------------


class TestFormatGpu:
    def test_no_accelerator_no_gpu(self):
        assert _format_gpu(None, None) is None

    def test_gpu_count_only(self):
        assert _format_gpu(None, 2) == "2"

    def test_accelerator_only(self):
        acc = MagicMock()
        acc.__str__ = lambda self: "nvidia-tesla-v100"
        assert _format_gpu(acc, None) == "nvidia-tesla-v100"

    def test_accelerator_with_count(self):
        acc = MagicMock()
        acc.__str__ = lambda self: "nvidia-tesla-v100"
        assert _format_gpu(acc, 4) == "nvidia-tesla-v100:4"


class TestFormatSharedMemory:
    def test_none(self):
        assert _format_shared_memory(None) is None

    def test_true(self):
        assert _format_shared_memory(True) == "auto"

    def test_string(self):
        assert _format_shared_memory("2Gi") == "2Gi"


class TestSetResourceFormat:
    def test_both_set(self):
        assert set_resource_format("1", "2") == ("1", "2")

    def test_only_request(self):
        assert set_resource_format("1", None) == "1"

    def test_only_limit(self):
        assert set_resource_format(None, "2") == "2"

    def test_neither_set(self):
        assert set_resource_format(None, None) is None


class TestMergeFlytekitRequestsAndLimits:
    def test_merges_cpu_and_mem(self):
        req = flytekit.Resources(cpu="1", mem="1Gi")
        lim = flytekit.Resources(cpu="2", mem="2Gi")
        result = _merge_flytekit_requests_and_limits_to_resources(req, lim)
        assert result.cpu == ("1", "2")
        assert result.mem == ("1Gi", "2Gi")

    def test_merges_with_empty_limits(self):
        req = flytekit.Resources(cpu="1")
        lim = flytekit.Resources()
        result = _merge_flytekit_requests_and_limits_to_resources(req, lim)
        assert result.cpu == "1"
        assert result.mem is None


class TestTransformResourceV1ToV2:
    def test_resources_and_requests_raises(self):
        with pytest.raises(ValueError, match="`resource` can not be used together"):
            _transform_resource_v1_to_v2(
                requests=flytekit.Resources(cpu="1"),
                resources=flytekit.Resources(cpu="2"),
            )

    def test_basic_requests_limits(self):
        result = _transform_resource_v1_to_v2(
            requests=flytekit.Resources(cpu="1", mem="1Gi"),
            limits=flytekit.Resources(cpu="2", mem="2Gi"),
        )
        assert isinstance(result, flyte.Resources)

    def test_with_shared_memory_true(self):
        result = _transform_resource_v1_to_v2(
            resources=flytekit.Resources(cpu="1"),
            shared_memory=True,
        )
        assert isinstance(result, flyte.Resources)


# ---------------------------------------------------------------------------
# _secret.py
# ---------------------------------------------------------------------------


class TestConvertSingleSecret:
    def test_env_var_mount(self):
        s = flytekit.Secret(key="my-key", group="my-group", env_var="MY_VAR")
        result = _convert_single_secret(s)
        assert isinstance(result, flyte.Secret)
        assert result.key == "my-key"
        assert result.group == "my-group"

    def test_file_mount_sets_mount_not_env_var(self):
        """When mount_requirement is FILE, mount should be /etc/flyte/secrets."""
        s = MagicMock(spec=flytekit.Secret)
        s.key = "my-key"
        s.group = "my-group"
        s.env_var = None
        s.mount_requirement = flytekit.Secret.MountType.FILE
        result = _convert_single_secret(s)
        assert isinstance(result, flyte.Secret)
        assert str(result.mount) == "/etc/flyte/secrets"
        assert result.as_env_var is None


class TestTransformSecretV1ToV2:
    def test_none_returns_none(self):
        assert _transform_secret_v1_to_v2(None) is None

    def test_empty_list_returns_none(self):
        assert _transform_secret_v1_to_v2([]) is None

    def test_single_secret(self):
        secrets = [flytekit.Secret(key="k1", group="g1")]
        result = _transform_secret_v1_to_v2(secrets)
        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], flyte.Secret)

    def test_multiple_secrets(self):
        secrets = [
            flytekit.Secret(key="k1", group="g1"),
            flytekit.Secret(key="k2", group="g2", env_var="V2"),
        ]
        result = _transform_secret_v1_to_v2(secrets)
        assert result is not None
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _pod_template.py
# ---------------------------------------------------------------------------


class TestTransformPodTemplateV1ToV2:
    def test_none_returns_none(self):
        assert _transform_pod_template_v1_to_v2(None) is None  # type: ignore[arg-type]

    def test_basic_transform(self):
        v1_template = flytekit.PodTemplate(
            primary_container_name="main",
            labels={"app": "test"},
            annotations={"note": "val"},
        )
        result = _transform_pod_template_v1_to_v2(v1_template)
        assert isinstance(result, flyte.PodTemplate)
        assert result.primary_container_name == "main"
        assert result.labels == {"app": "test"}
        assert result.annotations == {"note": "val"}


# ---------------------------------------------------------------------------
# _image.py — pure helper functions
# ---------------------------------------------------------------------------


class TestParsePythonVersion:
    def test_none(self):
        assert _parse_python_version(None) is None

    def test_major_minor(self):
        assert _parse_python_version("3.11") == (3, 11)

    def test_major_minor_patch(self):
        assert _parse_python_version("3.11.2") == (3, 11)

    def test_single_component(self):
        assert _parse_python_version("3") is None


class TestParsePlatform:
    def test_none(self):
        assert _parse_platform(None) is None

    def test_single(self):
        assert _parse_platform("linux/amd64") == ("linux/amd64",)

    def test_multiple(self):
        assert _parse_platform("linux/amd64, linux/arm64") == ("linux/amd64", "linux/arm64")


class TestTranslatePipPackages:
    def test_empty(self):
        assert _translate_pip_packages(None) == ["flytekit"]

    def test_regular_packages(self):
        result = _translate_pip_packages(["pandas", "numpy"])
        assert result == ["flytekit", "pandas", "numpy"]

    def test_plugin_translation_includes_both(self):
        """v2 package is added alongside v1 so remote containers can resolve v1 imports."""
        result = _translate_pip_packages(["flytekitplugins-spark", "pandas"])
        assert result == ["flytekit", _pin_to_flyte_version("flyteplugins-spark"), "flytekitplugins-spark", "pandas"]

    def test_plugin_with_version_specifier(self):
        result = _translate_pip_packages(["flytekitplugins-spark==1.16.3", "pandas>=2.0"])
        assert result == [
            "flytekit",
            _pin_to_flyte_version("flyteplugins-spark"),
            "flytekitplugins-spark==1.16.3",
            "pandas>=2.0",
        ]

    def test_plugin_with_various_specifiers(self):
        result = _translate_pip_packages(
            [
                "flytekitplugins-kfpytorch>=1.0,<2.0",
                "flytekitplugins-ray!=0.5",
                "flytekitplugins-dask~=1.2",
            ]
        )
        assert result == [
            "flytekit",
            _pin_to_flyte_version("flyteplugins-pytorch"),
            "flytekitplugins-kfpytorch>=1.0,<2.0",
            _pin_to_flyte_version("flyteplugins-ray"),
            "flytekitplugins-ray!=0.5",
            _pin_to_flyte_version("flyteplugins-dask"),
            "flytekitplugins-dask~=1.2",
        ]

    def test_all_known_plugins_includes_both(self):
        """Each v1 plugin produces both the v2 name and the original v1 name."""
        result = _translate_pip_packages(list(_PACKAGE_V1_TO_V2.keys()))
        expected = ["flytekit"]
        for v1, v2 in _PACKAGE_V1_TO_V2.items():
            expected.extend([_pin_to_flyte_version(v2), v1])
        assert result == expected


class TestBuildPipSecretMounts:
    def test_none(self):
        assert _build_pip_secret_mounts(None) is None

    def test_empty(self):
        assert _build_pip_secret_mounts([]) is None

    def test_single_mount(self):
        from pathlib import Path

        result = _build_pip_secret_mounts([("secret-key", "/etc/flyte/secrets")])
        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], flyte.Secret)
        assert result[0].key == "secret-key"
        assert result[0].mount == Path("/etc/flyte/secrets")


class TestExtractAttributes:
    def test_packages_merged(self):
        parent = flytekit.ImageSpec(packages=["a"])
        child = flytekit.ImageSpec(packages=["b", "c"])
        _extract_attributes(parent, child)
        assert "b" in parent.packages
        assert "c" in parent.packages

    def test_env_merged(self):
        parent = flytekit.ImageSpec(env={"A": "1"})
        child = flytekit.ImageSpec(env={"B": "2"})
        _extract_attributes(parent, child)
        assert parent.env == {"A": "1", "B": "2"}

    def test_commands_merged(self):
        parent = flytekit.ImageSpec(commands=["cmd1"])
        child = flytekit.ImageSpec(commands=["cmd2"])
        _extract_attributes(parent, child)
        assert "cmd2" in parent.commands

    def test_pip_extra_args_merged(self):
        parent = flytekit.ImageSpec()
        parent.pip_extra_args = "--no-deps"
        child = flytekit.ImageSpec()
        child.pip_extra_args = "--pre"
        _extract_attributes(parent, child)
        assert parent.pip_extra_args == "--no-deps --pre"

    def test_no_child_attributes(self):
        parent = flytekit.ImageSpec(packages=["a"])
        child = flytekit.ImageSpec()
        _extract_attributes(parent, child)
        assert parent.packages == ["a"]
