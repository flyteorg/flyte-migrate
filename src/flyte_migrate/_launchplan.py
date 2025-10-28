from typing import Any, Dict, Optional

import flytekit
from flyte import Cron, FixedRate, TaskEnvironment, Trigger
from flyte._logging import logger
from flyte._task import AsyncFunctionTaskTemplate
from flytekit.models import common as _common_models
from flytekit.models import schedule as _schedule_model

from ._workflow import parent_env


def merge_inputs(
    default_inputs: Optional[Dict[str, Any]] = None,
    fixed_inputs: Optional[Dict[str, Any]] = None,
) -> dict:
    if default_inputs is None and fixed_inputs is None:
        return {}
    if fixed_inputs is None:
        return default_inputs
    if default_inputs is None:
        return fixed_inputs
    return {**default_inputs, **fixed_inputs}


def schedule_to_trigger(
    name: str,
    schedule: Optional[_schedule_model.Schedule] = None,
    default_inputs: Optional[Dict[str, Any]] = None,
    fixed_inputs: Optional[Dict[str, Any]] = None,
    overwrite_cache: Optional[bool] = None,
    auto_activate: bool = False,
    labels: Optional[_common_models.Labels] = None,
    annotations: Optional[_common_models.Annotations] = None,
) -> Trigger:
    if schedule is None:
        return None
    if overwrite_cache is None:
        overwrite_cache = False
    labels = dict(labels.values.items()) if labels else None
    annotations = dict(annotations.values.items()) if annotations else None
    inputs = merge_inputs(default_inputs, fixed_inputs)

    if schedule.rate:
        automation = FixedRate(schedule.rate.value)
    elif schedule.cron_expression:
        automation = Cron(schedule.cron_expression)
    elif schedule.cron_schedule.schedule:
        automation = Cron(schedule.cron_schedule.schedule)
    else:
        raise ValueError(f"Unsupported schedule type: {schedule}")

    return Trigger(
        name=name,
        automation=automation,
        inputs=inputs,
        overwrite_cache=overwrite_cache,
        auto_activate=auto_activate,
        labels=labels,
        annotations=annotations,
    )


class LaunchPlanTransformer(object):
    @classmethod
    def create(
        cls,
        name: str,
        workflow: AsyncFunctionTaskTemplate,
        default_inputs: Optional[Dict[str, Any]] = None,
        fixed_inputs: Optional[Dict[str, Any]] = None,
        schedule: Optional[_schedule_model.Schedule] = None,
        overwrite_cache: Optional[bool] = None,
        auto_activate: bool = False,
        **kwargs,
    ) -> TaskEnvironment:
        if kwargs:
            logger.debug(f"Unsupported args in v2 trigger {kwargs.values()}")

        # Add trigger if it is not existed
        task_name = parent_env.name + "." + workflow.func.__name__
        if task_name in parent_env._tasks:
            triggers = parent_env._tasks[task_name].triggers
            for t in triggers:
                if t.name == name:
                    return parent_env

            trigger = schedule_to_trigger(
                name=name,
                schedule=schedule,
                default_inputs=default_inputs,
                fixed_inputs=fixed_inputs,
                overwrite_cache=overwrite_cache,
                auto_activate=auto_activate,
            )
            parent_env._tasks[task_name].triggers += (trigger,)
        return parent_env

    @classmethod
    def get_or_create(cls, **kwargs) -> TaskEnvironment:
        return cls.create(**kwargs)


flytekit.LaunchPlan = LaunchPlanTransformer
