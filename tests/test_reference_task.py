"""Tests for the reference_task shim (_reference.py)."""

import flytekit

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._reference import _SyncLazyEntity


class TestReferenceTaskShim:
    def test_flytekit_reference_task_is_patched(self):
        """flytekit.reference_task should be replaced by the shim."""
        from flyte_migrate._reference import reference_task_shim

        assert flytekit.reference_task is reference_task_shim

    def test_decorator_returns_lazy_entity(self):
        """Decorating a stub function should produce a v2 LazyEntity."""

        @flytekit.reference_task(
            project="my-project",
            domain="development",
            name="my_module.my_task",
            version="abc123",
        )
        def my_remote_task(a: str) -> str: ...

        assert isinstance(my_remote_task, _SyncLazyEntity)
        assert my_remote_task.name == "my_module.my_task"

    def test_stub_body_is_ignored(self):
        """The stub function body should never be executed."""

        @flytekit.reference_task(
            project="proj",
            domain="dev",
            name="some.task",
            version="v1",
        )
        def stub_task(x: int) -> int:
            raise RuntimeError("This should never run")

        # The result is a LazyEntity, not the original function
        assert isinstance(stub_task, _SyncLazyEntity)

    def test_version_optional_defaults_to_latest(self):
        """Omitting version should resolve via auto_version='latest' instead of raising."""

        @flytekit.reference_task(
            project="my-project",
            domain="development",
            name="my_module.my_task",
        )
        def latest_task(a: str) -> str: ...

        assert isinstance(latest_task, _SyncLazyEntity)
        assert latest_task.name == "my_module.my_task"

    def test_reference_launch_plan_is_patched(self):
        """flytekit.reference_launch_plan should be replaced by the shim."""
        from flyte_migrate._reference import reference_launch_plan_shim

        assert flytekit.reference_launch_plan is reference_launch_plan_shim

    def test_reference_launch_plan_returns_lazy_entity(self):
        """Decorating a stub with reference_launch_plan should produce a sync LazyEntity."""

        @flytekit.reference_launch_plan(
            project="my-project",
            domain="development",
            name="flytekit_workflow.my_wf",
        )
        def my_remote_lp(a: str) -> str: ...

        assert isinstance(my_remote_lp, _SyncLazyEntity)
        assert my_remote_lp.name == "flytekit_workflow.my_wf"

    def test_different_params_produce_different_entities(self):
        """Each reference_task call with different params should create a distinct entity."""

        @flytekit.reference_task(project="p1", domain="d1", name="task_a", version="v1")
        def task_a(x: int) -> int: ...

        @flytekit.reference_task(project="p2", domain="d2", name="task_b", version="v2")
        def task_b(x: int) -> int: ...

        assert task_a.name == "task_a"
        assert task_b.name == "task_b"
        assert task_a is not task_b
