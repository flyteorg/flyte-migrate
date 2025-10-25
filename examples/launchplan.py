import flyte_migrate  # noqa: F401, I001
import logging
from datetime import timedelta
from flytekit import task, dynamic, workflow, LaunchPlan, FixedRate, CronSchedule


@task(cache=True, cache_version="1.0", retries=3)
def say_hello(name: str):
    print(f"Hello, {name}!")

@dynamic()
def dynamic_task(name: str):
    say_hello(name=name)

@workflow
def wf(name: str):
    say_hello(name=name)
    dynamic_task(name=name)


lp = LaunchPlan.get_or_create(
    workflow=wf,
    name="v2_fixed_rate_trigger",
    default_inputs={"name": "flyte"},
    schedule=FixedRate(duration=timedelta(minutes=10)),
)


lp = LaunchPlan.get_or_create(
    workflow=wf,
    name="v2_cron_schedule_trigger",
    default_inputs={"name": "flyte"},
    schedule=CronSchedule(
        schedule="*/10 * * * *"
    )
)

if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    flyte.deploy(env)