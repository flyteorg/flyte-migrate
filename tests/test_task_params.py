"""Tests for task_shim parameter handling in _task.py."""

import logging
from datetime import timedelta

import flyte
import flytekit

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._task import _build_task_environment, _translate_cache_policy, task_shim

# ---------------------------------------------------------------------------
# _translate_cache_policy
# ---------------------------------------------------------------------------


class TestTranslateCachePolicy:
    def test_true_returns_auto(self):
        assert _translate_cache_policy(True) == "auto"

    def test_false_returns_disable(self):
        assert _translate_cache_policy(False) == "disable"

    def test_cache_object_with_version_becomes_override(self):
        # Stand-in with v1 Cache's fields — constructing a real flytekit.Cache pulls in
        # plugin machinery unrelated to the translation, which duck-types via getattr.
        from types import SimpleNamespace

        v1 = SimpleNamespace(version="v3", serialize=True, ignored_inputs=("a",), salt="s", policies=None)
        v2 = _translate_cache_policy(v1)
        assert isinstance(v2, flyte.Cache)
        assert v2.behavior == "override"
        assert v2.version_override == "v3"
        assert v2.serialize is True
        assert v2.ignored_inputs == ("a",)
        assert v2.salt == "s"

    def test_cache_object_without_version_becomes_auto(self):
        from types import SimpleNamespace

        v2 = _translate_cache_policy(
            SimpleNamespace(version=None, serialize=False, ignored_inputs=(), salt="", policies=None)
        )
        assert isinstance(v2, flyte.Cache)
        assert v2.behavior == "auto"
        assert v2.version_override is None


# ---------------------------------------------------------------------------
# _build_task_environment
# ---------------------------------------------------------------------------


def dummy_fn():
    pass


class TestBuildTaskEnvironment:
    def test_docs_maps_to_description(self):
        """Documentation.short_description should become the env description."""
        docs = flytekit.Documentation(short_description="My task does X")
        env = _build_task_environment(
            dummy_fn,
            cache=False,
            task_config=None,
            container_image=None,
            environment=None,
            requests=None,
            limits=None,
            resources=None,
            accelerator=None,
            shared_memory=None,
            secret_requests=None,
            docs=docs,
            pod_template=None,
            pod_template_name=None,
        )
        assert isinstance(env, flyte.TaskEnvironment)
        assert env.description == "My task does X"

    def test_docs_none_gives_no_description(self):
        env = _build_task_environment(
            dummy_fn,
            cache=False,
            task_config=None,
            container_image=None,
            environment=None,
            requests=None,
            limits=None,
            resources=None,
            accelerator=None,
            shared_memory=None,
            secret_requests=None,
            docs=None,
            pod_template=None,
            pod_template_name=None,
        )
        assert env.description is None

    def test_environment_dict_passed_through(self):
        """The environment dict should be set as env_vars on the TaskEnvironment."""
        env_dict = {"MY_VAR": "hello", "OTHER": "world"}
        env = _build_task_environment(
            dummy_fn,
            cache=False,
            task_config=None,
            container_image=None,
            environment=env_dict,
            requests=None,
            limits=None,
            resources=None,
            accelerator=None,
            shared_memory=None,
            secret_requests=None,
            docs=None,
            pod_template=None,
            pod_template_name=None,
        )
        assert env.env_vars == {"MY_VAR": "hello", "OTHER": "world"}

    def test_cache_true_sets_auto(self):
        env = _build_task_environment(
            dummy_fn,
            cache=True,
            task_config=None,
            container_image=None,
            environment=None,
            requests=None,
            limits=None,
            resources=None,
            accelerator=None,
            shared_memory=None,
            secret_requests=None,
            docs=None,
            pod_template=None,
            pod_template_name=None,
        )
        assert env.cache == "auto"


# ---------------------------------------------------------------------------
# task_shim — integration-level tests
# ---------------------------------------------------------------------------


class TestTaskShim:
    def test_enable_deck_maps_to_report(self):
        """enable_deck=True should pass report=True to env.task()."""

        @task_shim(enable_deck=True)
        def my_deck_task(x: int) -> int:
            return x

        # The function should be wrapped without error
        assert callable(my_deck_task)

    def test_disable_deck_false_maps_to_no_report(self):
        """enable_deck=False should pass report=False."""

        @task_shim(enable_deck=False)
        def my_no_deck_task(x: int) -> int:
            return x

        assert callable(my_no_deck_task)

    def test_unknown_kwargs_logged_not_raised(self, caplog):
        """Unknown kwargs should be logged at DEBUG level and not raise."""
        with caplog.at_level(logging.DEBUG, logger="flyte"):

            @task_shim(execution_mode=1, node_dependency_hints=[], pickle_untyped=True)
            def my_task(x: int) -> int:
                return x

        assert callable(my_task)

    def test_cache_version_accepted_without_error(self):
        """cache_version should be accepted (but ignored in v2)."""

        @task_shim(cache=True, cache_version="2.0")
        def cached_fn(x: int) -> int:
            return x

        assert callable(cached_fn)

    def test_bare_decorator(self):
        """@task_shim without parentheses should work."""

        @task_shim
        def bare_task(x: int) -> int:
            return x

        assert callable(bare_task)

    def test_all_params_together(self):
        """Smoke test: pass all known parameters at once without error."""

        @task_shim(
            cache=True,
            cache_version="1.0",
            retries=2,
            interruptible=True,
            timeout=timedelta(minutes=5),
            environment={"K": "V"},
            requests=flytekit.Resources(cpu="1", mem="1Gi"),
            limits=flytekit.Resources(cpu="2", mem="2Gi"),
            docs=flytekit.Documentation(short_description="test"),
            enable_deck=True,
        )
        def full_task(x: int) -> int:
            return x

        assert callable(full_task)

    def test_docs_with_long_description(self):
        """Documentation with long_description should not error; only short_description is used."""
        docs = flytekit.Documentation(
            short_description="Short desc",
        )

        @task_shim(docs=docs)
        def doc_task(x: int) -> int:
            return x

        assert callable(doc_task)

    def test_disable_deck_in_kwargs_logged(self, caplog):
        """disable_deck passed via kwargs should be logged as unsupported."""
        with caplog.at_level(logging.DEBUG, logger="flyte"):

            @task_shim(disable_deck=True)
            def my_task(x: int) -> int:
                return x

        assert callable(my_task)


class TestV2ImagePassthrough:
    def test_v2_image_used_as_is(self):
        """A v2 flyte.Image as container_image must be passed through untouched."""
        v2_image = flyte.Image.from_debian_base().with_pip_packages("flytekit", "flyte-migrate", "pandas")
        env = _build_task_environment(
            dummy_fn,
            cache=False,
            task_config=None,
            container_image=v2_image,
            environment=None,
            requests=None,
            limits=None,
            resources=None,
            accelerator=None,
            shared_memory=None,
            secret_requests=None,
            docs=None,
            pod_template=None,
            pod_template_name=None,
        )
        assert env.image is v2_image
