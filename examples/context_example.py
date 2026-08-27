"""Reading v2 execution metadata through v1's ``flytekit.current_context()``.

v1 code reaches for execution metadata via ``flytekit.current_context()``. The shim rewires
``ExecutionParameters``' properties onto ``flyte.ctx()``, so the same v1 calls return the real
v2 values.

The interesting part is what happens when the bridge is *not* in place: flytekit ships a
local-run safety net (``FlyteContextManager.initialize()``) that fills these in with
``local/local/local`` identifiers and local temp paths, so the reads succeed and return
well-formed, entirely fake values — no error, no warning. ``check_context`` therefore asserts
against that signature rather than just printing: on a cluster, a value of ``local`` means the
bridge is broken, not that the cluster is odd.

Two attributes have no v2 source at all — ``stats`` and ``execution_date`` — and log a warning
once on first read instead of silently standing in. ``show_gaps`` exercises that path.

    pyflyte-migrate run examples/context_example.py wf --name=flyte
    pyflyte-migrate run --remote examples/context_example.py wf --name=flyte
"""

import flyte_migrate  # noqa: F401, I001
import logging
from typing import Dict

from flytekit import current_context, task, workflow

# What flytekit's off-cluster fallback puts in these fields.
V1_LOCAL_PLACEHOLDER = "local"


@task
def check_context(name: str) -> Dict[str, str]:
    """Read the v2-backed attributes and fail loudly if any is still the v1 fallback."""
    ctx = current_context()

    execution_id = ctx.execution_id
    task_id = ctx.task_id
    raw_output_prefix = ctx.raw_output_prefix

    # ctx.logging is the v2 logger, so this lands in the task's logs on the cluster.
    ctx.logging.info(f"{name}: running as {execution_id.project}/{execution_id.domain}/{execution_id.name}")

    assert execution_id.name != V1_LOCAL_PLACEHOLDER, (
        f"execution_id.name is {execution_id.name!r} — the shim is not bridging to the v2 context"
    )
    assert execution_id.project != V1_LOCAL_PLACEHOLDER, (
        f"execution_id.project is {execution_id.project!r} — the shim is not bridging to the v2 context"
    )
    assert raw_output_prefix, "raw_output_prefix is empty"

    return {
        # execution_id identifies the run, task_id this one invocation within it — so these
        # two names differ, and every task in the run shares the execution_id.
        "execution_id.name": str(execution_id.name),
        "execution_id.project": str(execution_id.project),
        "execution_id.domain": str(execution_id.domain),
        "task_id.name": str(task_id.name),
        "task_id.version": str(task_id.version),
        "raw_output_prefix": str(raw_output_prefix),
    }


@task
def check_execution_id_is_shared(first: Dict[str, str], name: str) -> str:
    """A second task in the same run must report the same execution_id.

    This is the property v1 code actually relies on — the value is used as a run-level key for
    correlation, dedup and idempotency. Mapping it to v2's ``ActionID.name`` (one invocation)
    rather than ``run_name`` (the run) would hand each task a different id, and both are
    perfectly valid strings, so nothing would look wrong.
    """
    ctx = current_context()

    assert ctx.execution_id.name == first["execution_id.name"], (
        f"execution_id differs between tasks: {ctx.execution_id.name!r} vs {first['execution_id.name']!r}"
    )
    # ...while task_id does not, since this is a different invocation.
    assert ctx.task_id.name != first["task_id.name"], "task_id should differ between tasks"

    return f"{name}: execution_id {ctx.execution_id.name} shared, task_id {ctx.task_id.name} distinct"


@task
def show_gaps() -> str:
    """``stats`` and ``execution_date`` have no v2 equivalent; each warns once on first read.

    They still return v1's local value rather than raising — v1 code usually only logs these,
    and breaking an otherwise-working workflow over a log line is the worse trade. The warning
    is what keeps the gap visible.
    """
    ctx = current_context()

    ctx.stats.incr("flyte_migrate.example.counter")  # accepted, then discarded
    execution_date = ctx.execution_date

    # working_directory is deliberately left on v1's local path: its contract is "a local
    # scratch dir for this task", which a local temp dir already satisfies.
    return f"execution_date={execution_date.isoformat()} working_directory={ctx.working_directory}"


@workflow
def wf(name: str) -> str:
    first = check_context(name=name)
    shared = check_execution_id_is_shared(first=first, name=name)
    gaps = show_gaps()
    return f"{shared} | {gaps}"


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(wf, name="flyte")
    print(run.name)
    print(run.url)
