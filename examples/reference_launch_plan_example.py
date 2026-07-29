"""v1 ``@reference_launch_plan`` running on a v2 cluster.

References the ``greet_wf`` workflow registered by reference_task_target.py.
v1 workflows register as tasks in the ``flytekit_workflow`` environment, so the
launch plan name is ``flytekit_workflow.greet_wf``.
"""

import flyte_migrate  # noqa: F401, I001

from flytekit import reference_launch_plan, task, workflow


@reference_launch_plan(
    project="flyte-migrate",
    domain="development",
    name="flytekit_workflow.greet_wf",  # registered by reference_task_target.py
)
def remote_greet_lp(name: str) -> str:
    """Stub — this body is never executed. The real workflow runs on the cluster."""


@task
def shout(greeting: str) -> str:
    return greeting.upper()


@workflow
def reference_lp_wf(name: str) -> str:
    greeting = remote_greet_lp(name=name)
    return shout(greeting=greeting)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config()
    run = flyte.with_runcontext(mode="remote").run(reference_lp_wf, name="flyte")
    print(run.name)
    print(run.url)
