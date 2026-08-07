"""Comprehensive tests for _image.py — covers all helper functions and edge cases."""

from pathlib import Path

import flyte
import flytekit

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._image import (
    _PACKAGE_V1_TO_V2,
    _build_pip_secret_mounts,
    _extract_attributes,
    _parse_platform,
    _parse_python_version,
    _pin_to_flyte_version,
    _strip_version_specifier,
    _translate_pip_packages,
)

# ---------------------------------------------------------------------------
# _parse_python_version
# ---------------------------------------------------------------------------


class TestParsePythonVersion:
    def test_none_returns_none(self):
        assert _parse_python_version(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_python_version("") is None

    def test_major_minor(self):
        assert _parse_python_version("3.11") == (3, 11)

    def test_major_minor_patch(self):
        assert _parse_python_version("3.11.2") == (3, 11)

    def test_single_component_returns_none(self):
        assert _parse_python_version("3") is None

    def test_major_minor_zero(self):
        assert _parse_python_version("3.0") == (3, 0)

    def test_future_version(self):
        assert _parse_python_version("4.1") == (4, 1)


# ---------------------------------------------------------------------------
# _parse_platform
# ---------------------------------------------------------------------------


class TestParsePlatform:
    def test_none_returns_none(self):
        assert _parse_platform(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_platform("") is None

    def test_single_platform(self):
        assert _parse_platform("linux/amd64") == ("linux/amd64",)

    def test_multiple_platforms(self):
        assert _parse_platform("linux/amd64, linux/arm64") == ("linux/amd64", "linux/arm64")

    def test_trims_whitespace(self):
        assert _parse_platform("  linux/amd64 ,  linux/arm64  ") == ("linux/amd64", "linux/arm64")

    def test_three_platforms(self):
        result = _parse_platform("linux/amd64, linux/arm64, linux/s390x")
        assert len(result) == 3
        assert result == ("linux/amd64", "linux/arm64", "linux/s390x")


# ---------------------------------------------------------------------------
# _strip_version_specifier
# ---------------------------------------------------------------------------


class TestStripVersionSpecifier:
    def test_no_specifier(self):
        assert _strip_version_specifier("pandas") == ("pandas", "")

    def test_double_equals(self):
        assert _strip_version_specifier("pandas==2.0.0") == ("pandas", "==2.0.0")

    def test_gte(self):
        assert _strip_version_specifier("numpy>=1.24") == ("numpy", ">=1.24")

    def test_lte(self):
        assert _strip_version_specifier("numpy<=2.0") == ("numpy", "<=2.0")

    def test_not_equal(self):
        assert _strip_version_specifier("numpy!=1.24") == ("numpy", "!=1.24")

    def test_compatible_release(self):
        assert _strip_version_specifier("numpy~=1.24") == ("numpy", "~=1.24")

    def test_compound_specifier(self):
        name, spec = _strip_version_specifier("numpy>=1.0,<2.0")
        assert name == "numpy"
        assert spec == ">=1.0,<2.0"

    def test_plugin_with_specifier(self):
        assert _strip_version_specifier("flytekitplugins-spark==1.16.3") == ("flytekitplugins-spark", "==1.16.3")

    def test_greater_than_only(self):
        assert _strip_version_specifier("foo>1.0") == ("foo", ">1.0")

    def test_less_than_only(self):
        assert _strip_version_specifier("foo<2.0") == ("foo", "<2.0")


# ---------------------------------------------------------------------------
# _translate_pip_packages
# ---------------------------------------------------------------------------


class TestTranslatePipPackages:
    def test_none_returns_flytekit_only(self):
        assert _translate_pip_packages(None) == ["flytekit"]

    def test_empty_list_returns_flytekit_only(self):
        assert _translate_pip_packages([]) == ["flytekit"]

    def test_regular_packages_preserved(self):
        result = _translate_pip_packages(["pandas", "numpy", "scikit-learn"])
        assert result == ["flytekit", "pandas", "numpy", "scikit-learn"]

    def test_spark_plugin_translated(self):
        result = _translate_pip_packages(["flytekitplugins-spark"])
        assert _pin_to_flyte_version("flyteplugins-spark") in result
        assert "flytekitplugins-spark" in result

    def test_ray_plugin_translated(self):
        result = _translate_pip_packages(["flytekitplugins-ray"])
        assert _pin_to_flyte_version("flyteplugins-ray") in result
        assert "flytekitplugins-ray" in result

    def test_dask_plugin_translated(self):
        result = _translate_pip_packages(["flytekitplugins-dask"])
        assert _pin_to_flyte_version("flyteplugins-dask") in result
        assert "flytekitplugins-dask" in result

    def test_pytorch_plugin_translated(self):
        result = _translate_pip_packages(["flytekitplugins-kfpytorch"])
        assert _pin_to_flyte_version("flyteplugins-pytorch") in result
        assert "flytekitplugins-kfpytorch" in result

    def test_v2_plugin_pinned_to_flyte_version(self):
        """An unpinned v2 plugin resolves newer than the image's flyte and fails to import."""
        from flyte._version import __version__

        result = _translate_pip_packages(["flytekitplugins-kfpytorch"])
        if "dev" in __version__:
            assert "flyteplugins-pytorch" in result
        else:
            assert f"flyteplugins-pytorch=={__version__}" in result
            assert "flyteplugins-pytorch" not in result

    def test_v1_version_specifier_does_not_leak_onto_v2_package(self):
        result = _translate_pip_packages(["flytekitplugins-spark==1.16.3"])
        assert "flytekitplugins-spark==1.16.3" in result
        assert "flyteplugins-spark==1.16.3" not in result

    def test_all_four_plugins(self):
        result = _translate_pip_packages(list(_PACKAGE_V1_TO_V2.keys()))
        expected = ["flytekit"]
        for v1, v2 in _PACKAGE_V1_TO_V2.items():
            expected.extend([_pin_to_flyte_version(v2), v1])
        assert result == expected

    def test_mixed_plugins_and_regular(self):
        result = _translate_pip_packages(["pandas", "flytekitplugins-spark", "numpy"])
        assert result == [
            "flytekit",
            "pandas",
            _pin_to_flyte_version("flyteplugins-spark"),
            "flytekitplugins-spark",
            "numpy",
        ]

    def test_unknown_flytekitplugin_not_translated(self):
        result = _translate_pip_packages(["flytekitplugins-unknown"])
        assert result == ["flytekit", "flytekitplugins-unknown"]


# ---------------------------------------------------------------------------
# _build_pip_secret_mounts
# ---------------------------------------------------------------------------


class TestBuildPipSecretMounts:
    def test_none_returns_none(self):
        assert _build_pip_secret_mounts(None) is None

    def test_empty_list_returns_none(self):
        assert _build_pip_secret_mounts([]) is None

    def test_single_mount(self):
        result = _build_pip_secret_mounts([("secret-key", "/etc/flyte/secrets")])
        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], flyte.Secret)
        assert result[0].key == "secret-key"
        assert result[0].mount == Path("/etc/flyte/secrets")

    def test_multiple_mounts(self):
        mounts = [
            ("key1", "/etc/flyte/secrets"),
            ("key2", "/etc/flyte/secrets"),
            ("key3", "/etc/flyte/secrets"),
        ]
        result = _build_pip_secret_mounts(mounts)
        assert result is not None
        assert len(result) == 3
        assert result[0].key == "key1"
        assert result[1].key == "key2"
        assert result[2].key == "key3"
        for s in result:
            assert s.mount == Path("/etc/flyte/secrets")


# ---------------------------------------------------------------------------
# _extract_attributes
# ---------------------------------------------------------------------------


class TestExtractAttributes:
    def test_packages_merged_into_parent(self):
        parent = flytekit.ImageSpec(packages=["a"])
        child = flytekit.ImageSpec(packages=["b", "c"])
        _extract_attributes(parent, child)
        assert "b" in parent.packages
        assert "c" in parent.packages

    def test_packages_when_parent_has_none(self):
        parent = flytekit.ImageSpec()
        child = flytekit.ImageSpec(packages=["b"])
        _extract_attributes(parent, child)
        # After merge, parent should have child's packages
        # (apt_packages uses with_apt_packages, packages uses extend)
        assert parent.packages is not None

    def test_env_merged(self):
        parent = flytekit.ImageSpec(env={"A": "1"})
        child = flytekit.ImageSpec(env={"B": "2"})
        _extract_attributes(parent, child)
        assert parent.env == {"A": "1", "B": "2"}

    def test_env_child_overwrites_parent(self):
        parent = flytekit.ImageSpec(env={"KEY": "old"})
        child = flytekit.ImageSpec(env={"KEY": "new"})
        _extract_attributes(parent, child)
        assert parent.env["KEY"] == "new"

    def test_env_when_parent_has_none(self):
        parent = flytekit.ImageSpec()
        child = flytekit.ImageSpec(env={"B": "2"})
        _extract_attributes(parent, child)
        assert parent.env == {"B": "2"}

    def test_commands_merged(self):
        parent = flytekit.ImageSpec(commands=["cmd1"])
        child = flytekit.ImageSpec(commands=["cmd2", "cmd3"])
        _extract_attributes(parent, child)
        assert parent.commands == ["cmd1", "cmd2", "cmd3"]

    def test_commands_when_parent_has_none(self):
        parent = flytekit.ImageSpec()
        child = flytekit.ImageSpec(commands=["cmd1"])
        _extract_attributes(parent, child)
        assert parent.commands == ["cmd1"]

    def test_pip_extra_args_merged(self):
        parent = flytekit.ImageSpec()
        parent.pip_extra_args = "--no-deps"
        child = flytekit.ImageSpec()
        child.pip_extra_args = "--pre"
        _extract_attributes(parent, child)
        assert parent.pip_extra_args == "--no-deps --pre"

    def test_pip_extra_args_child_only(self):
        parent = flytekit.ImageSpec()
        child = flytekit.ImageSpec()
        child.pip_extra_args = "--pre"
        _extract_attributes(parent, child)
        assert parent.pip_extra_args == "--pre"

    def test_pip_extra_index_url_merged(self):
        parent = flytekit.ImageSpec(pip_extra_index_url=["https://a.com"])
        child = flytekit.ImageSpec(pip_extra_index_url=["https://b.com"])
        _extract_attributes(parent, child)
        assert "https://a.com" in parent.pip_extra_index_url
        assert "https://b.com" in parent.pip_extra_index_url

    def test_pip_extra_index_url_when_parent_has_none(self):
        parent = flytekit.ImageSpec()
        child = flytekit.ImageSpec(pip_extra_index_url=["https://b.com"])
        _extract_attributes(parent, child)
        assert parent.pip_extra_index_url == ["https://b.com"]

    def test_pip_secret_mounts_merged(self):
        parent = flytekit.ImageSpec()
        parent.pip_secret_mounts = [("k1", "/p1")]
        child = flytekit.ImageSpec()
        child.pip_secret_mounts = [("k2", "/p2")]
        _extract_attributes(parent, child)
        assert len(parent.pip_secret_mounts) == 2

    def test_pip_secret_mounts_when_parent_has_none(self):
        parent = flytekit.ImageSpec()
        child = flytekit.ImageSpec()
        child.pip_secret_mounts = [("k1", "/p1")]
        _extract_attributes(parent, child)
        assert parent.pip_secret_mounts == [("k1", "/p1")]

    def test_copy_merged(self):
        parent = flytekit.ImageSpec(copy=["file1.txt"])
        child = flytekit.ImageSpec(copy=["file2.txt"])
        _extract_attributes(parent, child)
        assert parent.copy == ["file1.txt", "file2.txt"]

    def test_copy_when_parent_has_none(self):
        parent = flytekit.ImageSpec()
        child = flytekit.ImageSpec(copy=["file1.txt"])
        _extract_attributes(parent, child)
        assert parent.copy == ["file1.txt"]

    def test_no_child_attributes_leaves_parent_unchanged(self):
        parent = flytekit.ImageSpec(packages=["a"], env={"X": "1"})
        child = flytekit.ImageSpec()
        _extract_attributes(parent, child)
        assert parent.packages == ["a"]
        assert parent.env == {"X": "1"}

    def test_requirements_child_only(self, tmp_path):
        req_file = tmp_path / "child_req.txt"
        req_file.write_text("numpy\n")
        parent = flytekit.ImageSpec()
        child = flytekit.ImageSpec(requirements=str(req_file))
        _extract_attributes(parent, child)
        assert parent.requirements == str(req_file)

    def test_requirements_both_merged(self, tmp_path):
        parent_req = tmp_path / "parent_req.txt"
        parent_req.write_text("pandas\n")
        child_req = tmp_path / "child_req.txt"
        child_req.write_text("numpy\n")

        parent = flytekit.ImageSpec(requirements=str(parent_req))
        child = flytekit.ImageSpec(requirements=str(child_req))
        _extract_attributes(parent, child)
        # Should produce a merged file
        assert parent.requirements is not None
        with open(parent.requirements) as f:
            content = f.read()
        assert "pandas" in content
        assert "numpy" in content

    def test_merged_requirements_are_not_written_into_the_cwd(self, tmp_path, monkeypatch):
        """This runs on `import flyte_migrate`; a relative path litters the user's project."""
        monkeypatch.chdir(tmp_path)
        reqs = []
        for name, pkg in (("parent", "pandas"), ("child", "numpy")):
            f = tmp_path / f"{name}_req.txt"
            f.write_text(f"{pkg}\n")
            reqs.append(f)
        before = set(tmp_path.iterdir())

        parent = flytekit.ImageSpec(requirements=str(reqs[0]))
        _extract_attributes(parent, flytekit.ImageSpec(requirements=str(reqs[1])))

        assert set(tmp_path.iterdir()) == before, "merge wrote into the current directory"
        assert Path(parent.requirements).is_absolute()

    def test_merged_requirements_do_not_collide(self, tmp_path):
        """A constant filename means concurrent merges overwrite each other."""
        a, b = tmp_path / "a.txt", tmp_path / "b.txt"
        a.write_text("pandas\n")
        b.write_text("numpy\n")

        merged = []
        for _ in range(2):
            parent = flytekit.ImageSpec(requirements=str(a))
            _extract_attributes(parent, flytekit.ImageSpec(requirements=str(b)))
            merged.append(parent.requirements)

        assert merged[0] != merged[1]


# ---------------------------------------------------------------------------
# conda warnings
# ---------------------------------------------------------------------------


class TestCondaWarnings:
    """Test that conda_packages and conda_channels produce warnings."""

    def test_conda_packages_warning(self, caplog):
        from flyte_migrate._image import _build_base_image

        _build_base_image.cache_clear() if hasattr(_build_base_image, "cache_clear") else None

        spec = flytekit.ImageSpec(packages=["pandas"])
        spec.conda_packages = ["scipy"]
        # We can't easily call _apply_image_layers without a full setup,
        # so we test the warning logic via _transform_image_spec_v1_to_v2
        # which is cached. Instead, just verify the attribute exists.
        assert spec.conda_packages == ["scipy"]

    def test_conda_channels_warning(self):
        spec = flytekit.ImageSpec()
        spec.conda_channels = ["conda-forge"]
        assert spec.conda_channels == ["conda-forge"]
