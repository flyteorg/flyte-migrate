import flyte_migrate  # noqa: F401, I001
from flytekit import task, workflow, LaunchPlan, CronSchedule

@task(cache=True, cache_version="1.0", retries=3)
def say_hello(name: str):
    print(f"Hello, {name}!")


@workflow
def wf(name: str):
    say_hello(name=name)
    dynamic_task(name=name)

env = LaunchPlan.get_or_create(
    workflow=wf,
    name="with_defaults",
    default_inputs={"name": "flyte"},
    schedule=CronSchedule(schedule="*/10 * * * *")
)

if __name__ == "__main__":
    """
    uv pip install -e .  # flyte-migrate
    uv pip install -e .  # flyte-sdk
    python examples/hello.py
    """
    import flyte

    flyte.init_from_config(path_or_config="config.yaml")
    print(flyte_migrate._task.parent_env._tasks)
