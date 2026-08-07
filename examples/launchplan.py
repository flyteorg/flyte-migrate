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
    schedule=FixedRate(duration=timedelta(hours=4)),
    auto_activate=True,
)


lp = LaunchPlan.get_or_create(
    workflow=wf,
    name="v2_cron_schedule_trigger",
    default_inputs={"name": "flyte"},
    schedule=CronSchedule(schedule="0 */4 * * *"),
    auto_activate=True,
)

if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    flyte.deploy(lp)
