import flyte_migrate  # noqa: F401, I001
import logging

from flytekit import LaunchPlan, task, workflow


@task
def greet(name: str, greeting: str) -> str:
    """Create a greeting message."""
    return f"{greeting}, {name}!"


@task
def format_output(message: str, uppercase: bool) -> str:
    """Format the output message."""
    if uppercase:
        return message.upper()
    return message


@workflow
def greeting_wf(name: str = "World", greeting: str = "Hello", uppercase: bool = False) -> str:
    """
    A simple greeting workflow.

    Demonstrates using LaunchPlans to create pre-configured
    workflow invocations with fixed or default inputs.
    """
    msg = greet(name=name, greeting=greeting)
    result = format_output(message=msg, uppercase=uppercase)
    return result


# Note: LaunchPlan.get_or_create is not yet fully supported with flyte-migrate.
# The LaunchPlan API is being shimmed. For now, use the workflow directly with
# different input parameters.
#
# In v1, you would create LaunchPlans like this:
# loud_greeting = LaunchPlan.get_or_create(
#     workflow=greeting_wf,
#     name="loud_greeting",
#     fixed_inputs={"uppercase": True},
#     default_inputs={"greeting": "Hey"},
# )
#
# For now, just call the workflow with the desired inputs:
# flyte.with_runcontext(mode="remote").run(greeting_wf, name="World", greeting="Hey", uppercase=True)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(
        greeting_wf, name="Flyte", greeting="Welcome", uppercase=True
    )
    print(run.name)
    print(run.url)
