"""v1 ``@reference_workflow`` running on a v2 cluster.

References the ``greet_wf`` workflow deployed by reference_task_target.py
(shimmed v1 workflows register as tasks named ``flytekit_workflow.<wf_name>``).
"""

import flyte_migrate  # noqa: F401, I001

from flytekit import reference_workflow, task, workflow


@reference_workflow(
    project="flyte-migrate",
    domain="development",
    name="flytekit_workflow.greet_wf",  # deployed by reference_task_target.py
)
def remote_greet_wf(name: str) -> str:
    """Stub — this body is never executed. The real workflow runs on the cluster."""


@task
def exclaim(greeting: str) -> str:
    return f"{greeting}!!!"


@workflow
def reference_workflow_wf(name: str) -> str:
    greeting = remote_greet_wf(name=name)
    return exclaim(greeting=greeting)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config()
    run = flyte.with_runcontext(mode="remote").run(reference_workflow_wf, name="flyte")
    print(run.name)
    print(run.url)
