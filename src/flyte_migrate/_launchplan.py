from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import flytekit

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
    def get_or_create(
        cls,
        workflow,
        name: Optional[str] = None,
        default_inputs: Optional[Dict[str, Any]] = None,
        fixed_inputs: Optional[Dict[str, Any]] = None,
        schedule: Optional[_schedule_model.Schedule] = None,
        labels: Optional[_common_models.Labels] = None,
        annotations: Optional[_common_models.Annotations] = None,
        overwrite_cache: Optional[bool] = None,
        auto_activate: bool = False,
    ) -> TaskEnvironment:
        trigger = Schedule_to_trigger(schedule)
        workflow.triggers = (trigger,)
        return workflow

flytekit.LaunchPlan = launchPlan_transformer
