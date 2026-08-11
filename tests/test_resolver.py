"""Shimmed tasks must carry MigrateTaskResolver so the container applies the shim before
importing user modules that lack the `import flyte_migrate` line (the pyflyte-migrate case)."""

import flytekit

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._resolver import MigrateTaskResolver


@flytekit.task
def a_task(name: str) -> str:
    return name


@flytekit.workflow
def a_wf(name: str) -> str:
    return a_task(name=name)


def test_task_and_workflow_carry_migrate_resolver():
    for tmpl in (a_task, a_wf):
        assert isinstance(tmpl.task_resolver, MigrateTaskResolver)
        assert tmpl.task_resolver.import_path == "flyte_migrate._resolver.MigrateTaskResolver"


def test_resolver_round_trips_via_container_path():
    # Same code path a0 runs: load_class(import_path) then load_task(loader_args).
    from flyte._internal.runtime.entrypoints import load_class

    resolver = load_class(a_task.task_resolver.import_path)()
    loaded = resolver.load_task(["mod", __name__, "instance", "a_task"])
    assert loaded is a_task
