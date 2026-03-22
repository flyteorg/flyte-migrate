import flyte_migrate  # noqa: F401, I001
import logging
from datetime import timedelta

from flytekit import CronSchedule, FixedRate, LaunchPlan, task, workflow


@task(cache=True, cache_version="1.0", retries=2)
def greet(name: str, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}!"


@task
def count_chars(text: str) -> int:
    return len(text)


@workflow
def greeting_wf(name: str = "world", greeting: str = "Hello") -> int:
    message = greet(name=name, greeting=greeting)
    return count_chars(text=message)


# ---------------------------------------------------------------------------
# 1. LaunchPlan with CronSchedule
# ---------------------------------------------------------------------------

cron_lp = LaunchPlan.create(
    name="greeting_cron_trigger",
    workflow=greeting_wf,
    default_inputs={"name": "cron-user"},
    schedule=CronSchedule(schedule="0 */6 * * *"),  # every 6 hours
    auto_activate=False,
)

# ---------------------------------------------------------------------------
# 2. LaunchPlan with FixedRate schedule
# ---------------------------------------------------------------------------

fixed_rate_lp = LaunchPlan.create(
    name="greeting_fixed_rate_trigger",
    workflow=greeting_wf,
    default_inputs={"name": "fixed-rate-user"},
    schedule=FixedRate(duration=timedelta(hours=1)),
    auto_activate=False,
)

# ---------------------------------------------------------------------------
# 3. LaunchPlan with default_inputs only
# ---------------------------------------------------------------------------

defaults_lp = LaunchPlan.create(
    name="greeting_defaults_only",
    workflow=greeting_wf,
    default_inputs={"name": "default-user", "greeting": "Hi"},
)

# ---------------------------------------------------------------------------
# 4. LaunchPlan with fixed_inputs only
# ---------------------------------------------------------------------------

fixed_lp = LaunchPlan.create(
    name="greeting_fixed_only",
    workflow=greeting_wf,
    fixed_inputs={"name": "fixed-user", "greeting": "Hey"},
)

# ---------------------------------------------------------------------------
# 5. LaunchPlan with both default_inputs and fixed_inputs
# ---------------------------------------------------------------------------

combined_lp = LaunchPlan.create(
    name="greeting_combined_inputs",
    workflow=greeting_wf,
    default_inputs={"name": "default-name"},
    fixed_inputs={"greeting": "Howdy"},
)

# ---------------------------------------------------------------------------
# 6. LaunchPlan with auto_activate=True
# ---------------------------------------------------------------------------

auto_lp = LaunchPlan.create(
    name="greeting_auto_activate",
    workflow=greeting_wf,
    default_inputs={"name": "auto-user"},
    schedule=CronSchedule(schedule="0 0 * * *"),  # daily at midnight
    auto_activate=True,
)

# ---------------------------------------------------------------------------
# 7. LaunchPlan.get_or_create() (alias for create)
# ---------------------------------------------------------------------------

alias_lp = LaunchPlan.get_or_create(
    name="greeting_get_or_create",
    workflow=greeting_wf,
    default_inputs={"name": "alias-user"},
    schedule=FixedRate(duration=timedelta(minutes=30)),
    auto_activate=False,
)

if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    # Deploy the last launch plan (which has a schedule) to register on the cluster
    flyte.deploy(alias_lp)
