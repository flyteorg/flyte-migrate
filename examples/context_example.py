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


@workflow
def wf(name: str) -> Dict[str, str]:
    return check_context(name=name)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(wf, name="flyte")
    print(run.name)
    print(run.url)
