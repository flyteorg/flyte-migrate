import flyte_migrate  # noqa: F401, I001
import logging

from flytekit import reference_task, task, workflow


@reference_task(
    project="flyte-migrate",
    domain="development",
    name="greet_env.greet",
    version="3472fed99486b72069b1f9b80ec76bf6",
)
def remote_greet(name: str) -> str:
    """Stub — this body is never executed. The real task runs on the cluster."""


@task
def format_greeting(greeting: str) -> str:
    return f"Got from remote: {greeting}"


@workflow
def reference_wf(name: str) -> str:
    greeting = remote_greet(name=name)
    return format_greeting(greeting=greeting)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(reference_wf, name="flyte")
    print(run.name)
    print(run.url)
