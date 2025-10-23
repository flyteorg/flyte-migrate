from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import flytekit

from ._workflow import parent_env
import flyte
from flyte import Image, Resources, TaskEnvironment, Trigger, Cron, FixedRate
from flytekit.core import workflow as _annotated_workflow
from flytekit.models import common as _common_models
from flytekit.models import schedule as _schedule_model

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
    schedule: Optional[_schedule_model.Schedule] = None,
    default_inputs: Optional[Dict[str, Any]] = None,
    fixed_inputs: Optional[Dict[str, Any]] = None,
) -> Optional[Trigger]:
    if schedule is None:
        return None
    inputs = merge_inputs(default_inputs, fixed_inputs)
    if schedule.rate is not None:
        return Trigger(
            name="my_fixed_rate_trigger",
            automation=FixedRate(schedule.rate.value),
            default_inputs=inputs,
        )
    elif schedule.cron_expression is not None:
        return Trigger(
            name="my_cron_trigger",
            automation=Cron(schedule.cron_expression),
            default_inputs=inputs,
        )
    else:
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
        notifications: Optional[List[_common_models.Notification]] = None,
        labels: Optional[_common_models.Labels] = None,
        annotations: Optional[_common_models.Annotations] = None,
        raw_output_data_config: Optional[_common_models.RawOutputDataConfig] = None,
        max_parallelism: Optional[int] = None,
        security_context: Optional[security.SecurityContext] = None,
        auth_role: Optional[_common_models.AuthRole] = None,
        trigger: Optional[LaunchPlanTriggerBase] = None,
        overwrite_cache: Optional[bool] = None,
        auto_activate: bool = False,
        concurrency: Optional[ConcurrencyPolicy] = None,
    ) -> TaskEnvironment:
        task_name = parent_env.name + '.' + workflow.func.__name__
        trigger = schedule_to_trigger(schedule)
        if task_name in parent_env._tasks.keys():
            parent_env._tasks[task_name].triggers=(trigger,)
        return parent_env

    @classmethod
    def get_or_create(
        cls,
        workflow: _annotated_workflow.WorkflowBase,
        name: Optional[str] = None,
        default_inputs: Optional[Dict[str, Any]] = None,
        fixed_inputs: Optional[Dict[str, Any]] = None,
        schedule: Optional[_schedule_model.Schedule] = None,
        notifications: Optional[List[_common_models.Notification]] = None,
        labels: Optional[_common_models.Labels] = None,
        annotations: Optional[_common_models.Annotations] = None,
        raw_output_data_config: Optional[_common_models.RawOutputDataConfig] = None,
        max_parallelism: Optional[int] = None,
        security_context: Optional[security.SecurityContext] = None,
        auth_role: Optional[_common_models.AuthRole] = None,
        trigger: Optional[LaunchPlanTriggerBase] = None,
        overwrite_cache: Optional[bool] = None,
        auto_activate: bool = False,
        concurrency: Optional[ConcurrencyPolicy] = None,
    ) -> TaskEnvironment:
        task_name = parent_env.name + '.' + workflow.func.__name__
        trigger = schedule_to_trigger(schedule)
        if task_name in parent_env._tasks.keys():
            parent_env._tasks[task_name].triggers=(trigger,)
        return parent_env

flytekit.LaunchPlan = launchPlan_transformer
