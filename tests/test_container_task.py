"""Tests for the v1 ContainerTask -> v2 flyte.extras.ContainerTask shim."""

from types import SimpleNamespace

import flytekit
from flyte.extras import ContainerTask as V2ContainerTask

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._container_task import _translate_metadata, container_task_shim
from flyte_migrate._workflow import parent_env_for


class TestPatching:
    def test_flytekit_container_task_is_patched(self):
        assert flytekit.ContainerTask is container_task_shim


class TestConstruction:
    def test_returns_registered_v2_container_task(self):
        ct = flytekit.ContainerTask(
            name="calculate-ellipse-area",
            image="python:3.12-slim",
            command=["python", "calc.py", "{{.inputs.a}}", "/var/outputs"],
            inputs={"a": float},
            outputs={"area": float},
        )
        assert isinstance(ct, V2ContainerTask)
        parent_env = parent_env_for(__name__)
        assert ct.name == f"{parent_env.name}.calculate-ellipse-area"
        assert ct.short_name == "calculate-ellipse-area"
        assert parent_env._tasks[ct.name] is ct

    def test_resources_and_metadata_format_translated(self):
        ct = flytekit.ContainerTask(
            name="with-resources",
            image="alpine",
            command=["echo", "hi"],
            requests=flytekit.Resources(cpu="1", mem="1Gi"),
            metadata_format=flytekit.core.container_task.ContainerTask.MetadataFormat.YAML,
        )
        assert ct.resources is not None
        assert ct._metadata_format == "YAML"

    def test_v1_metadata_maps_to_task_fields(self):
        ct = flytekit.ContainerTask(
            name="with-metadata",
            image="alpine",
            command=["echo", "hi"],
            metadata=flytekit.TaskMetadata(retries=3, interruptible=True),
        )
        assert ct.retries.count == 3  # v2 normalizes an int into RetryStrategy
        assert ct.interruptible is True


class TestTranslateMetadata:
    def test_none_gives_empty(self):
        assert _translate_metadata(None) == {}

    def test_cache_with_version_becomes_override(self):
        md = SimpleNamespace(
            retries=0,
            timeout=None,
            interruptible=None,
            cache=True,
            cache_version="v2",
            cache_serialize=True,
            cache_ignore_input_vars=("a",),
        )
        out = _translate_metadata(md)
        assert out["cache"].behavior == "override"
        assert out["cache"].version_override == "v2"
        assert out["cache"].serialize is True
        assert out["cache"].ignored_inputs == ("a",)
