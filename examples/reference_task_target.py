"""Target workflow for the reference_task / reference_launch_plan examples.

Run this first — it deploys ``greet_env.greet`` and ``flytekit_workflow.greet_wf``
to the cluster, which the reference examples then invoke. Note: tasks must be
*deployed* (not just run) to be resolvable by reference.
"""

import flyte_migrate  # noqa: I001

from flytekit import task, workflow


@task
def greet(name: str) -> str:
    return f"Hello, {name}!"


@workflow
def greet_wf(name: str) -> str:
    return greet(name=name)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config()
    deployments = flyte_migrate.deploy()
    print(deployments[0].summary_repr())
