"""Target workflow for reference_task_example.py.

Run this first — it registers ``greet_env.greet`` on the cluster, which
reference_task_example.py then invokes as a v1 ``@reference_task``.
"""

import flyte_migrate  # noqa: F401, I001

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
    run = flyte.with_runcontext(mode="remote").run(greet_wf, name="flyte")
    print(run.name)
    print(run.url)
