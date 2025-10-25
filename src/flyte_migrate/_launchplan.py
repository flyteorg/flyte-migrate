from __future__ import annotations

from typing import Any, Dict, Optional

import flytekit
from flyte import Cron, FixedRate, TaskEnvironment, Trigger
from flyte._logging import logger
from flytekit.core import workflow as _annotated_workflow
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
    overwrite_cache: bool = False,
    labels: Optional[_common_models.Labels] = None,
    annotations: Optional[_common_models.Annotations] = None,
) -> Optional[Trigger]:
    if schedule is None:
        return None

    labels = {k: v for k, v in labels.values.items()} if labels else None
    annotations = {k: v for k, v in annotations.values.items()} if annotations else None
    inputs = merge_inputs(default_inputs, fixed_inputs)

    automation = None
    if schedule.rate:
        automation = FixedRate(schedule.rate.value)
    elif schedule.cron_expression:
        automation = Cron(schedule.cron_expression)
    elif schedule.cron_schedule.schedule:
        automation = Cron(schedule.cron_schedule.schedule)

    if automation:
        return Trigger(
            name=name,
            automation=automation,
            inputs=inputs,
            overwrite_cache=overwrite_cache,
            labels=labels,
            annotations=annotations,
        )
    return None

class launchPlan_transformer(object):
    @classmethod
    def create(
        cls,
        name: str,
        workflow: _annotated_workflow.WorkflowBase,
        default_inputs: Optional[Dict[str, Any]] = None,
        fixed_inputs: Optional[Dict[str, Any]] = None,
        schedule: Optional[_schedule_model.Schedule] = None,
        # notifications: Optional[List[_common_models.Notification]] = None,
        labels: Optional[_common_models.Labels] = None,
        annotations: Optional[_common_models.Annotations] = None,
        # raw_output_data_config: Optional[_common_models.RawOutputDataConfig] = None,
        # max_parallelism: Optional[int] = None,
        # security_context: Optional[security.SecurityContext] = None,
        # auth_role: Optional[_common_models.AuthRole] = None,
        # trigger: Optional[LaunchPlanTriggerBase] = None,
        overwrite_cache: Optional[bool] = None,
        auto_activate: bool = False,
        # concurrency: Optional[ConcurrencyPolicy] = None,
        **kwargs,
    ) -> TaskEnvironment:
        if kwargs:
            logger.debug(f"Unsupported args {kwargs.values()}")
        task_name = parent_env.name + "." + workflow.func.__name__
        trigger = schedule_to_trigger(name, schedule, default_inputs, fixed_inputs)
        if task_name in parent_env._tasks.keys():
            triggers = parent_env._tasks[task_name].triggers
            if triggers is None:
                triggers = (trigger, )
            else:
                triggers += (trigger, )
            parent_env._tasks[task_name].triggers = triggers
        return parent_env

    @classmethod
    def get_or_create(
        cls,
        workflow: _annotated_workflow.WorkflowBase,
        name: Optional[str] = None,
        default_inputs: Optional[Dict[str, Any]] = None,
        fixed_inputs: Optional[Dict[str, Any]] = None,
        schedule: Optional[_schedule_model.Schedule] = None,
        # notifications: Optional[List[_common_models.Notification]] = None,
        labels: Optional[_common_models.Labels] = None,
        annotations: Optional[_common_models.Annotations] = None,
        # raw_output_data_config: Optional[_common_models.RawOutputDataConfig] = None,
        # max_parallelism: Optional[int] = None,
        # security_context: Optional[security.SecurityContext] = None,
        # auth_role: Optional[_common_models.AuthRole] = None,
        # trigger: Optional[LaunchPlanTriggerBase] = None,
        overwrite_cache: Optional[bool] = None,
        auto_activate: bool = False,
        # concurrency: Optional[ConcurrencyPolicy] = None,
        **kwargs,
    ) -> TaskEnvironment:
        if kwargs:
            logger.debug(f"Unsupported args {kwargs.values()}")
        task_name = parent_env.name + "." + workflow.func.__name__
        trigger = schedule_to_trigger(name, schedule, default_inputs, fixed_inputs)
        if task_name in parent_env._tasks.keys():
            triggers = parent_env._tasks[task_name].triggers
            if triggers is None:
                triggers = (trigger, )
            else:
                triggers += (trigger, )
            parent_env._tasks[task_name].triggers = triggers
        return parent_env


flytekit.LaunchPlan = launchPlan_transformer
