"""Transform v1 ``flytekit.LaunchPlan`` into v2 ``Trigger`` objects.

FlyteKit v1 uses ``LaunchPlan.create()`` / ``LaunchPlan.get_or_create()`` to
attach schedules (cron or fixed-rate) to workflows.  In v2, the equivalent
concept is a ``Trigger`` attached to a ``TaskEnvironment``.

This module provides:

- ``merge_inputs`` -- combine default and fixed inputs into a single dict.
- ``schedule_to_trigger`` -- convert a v1 ``Schedule`` model into a v2
  ``Trigger`` with the appropriate ``Cron`` or ``FixedRate`` automation.
- ``LaunchPlanTransformer`` -- drop-in replacement for ``flytekit.LaunchPlan``
  that creates or retrieves triggers on the parent ``TaskEnvironment``.
"""

from typing import Any, Dict, List, Optional, Tuple, Union

import flytekit
from flyte import TaskEnvironment
from flyte._logging import logger
from flyte._task import AsyncFunctionTaskTemplate
from flyte._trigger import Cron, FixedRate, Trigger
from flyte.models import ActionPhase
from flyte.notify import Email, Notification
from flytekit.models import common as _common_models
from flytekit.models import schedule as _schedule_model
from flytekit.models.core.execution import WorkflowExecutionPhase

from ._workflow import parent_env_for

# v1 notification phases are ints; v2 wants ActionPhase values. Only terminal phases
# are valid for v1 notifications.
_PHASE_V1_TO_V2 = {
    WorkflowExecutionPhase.SUCCEEDED: ActionPhase.SUCCEEDED,
    WorkflowExecutionPhase.FAILED: ActionPhase.FAILED,
    WorkflowExecutionPhase.TIMED_OUT: ActionPhase.TIMED_OUT,
    WorkflowExecutionPhase.ABORTED: ActionPhase.ABORTED,
}


def _translate_notifications(
    notifications: Optional[List[_common_models.Notification]],
) -> Optional[Tuple[Notification, ...]]:
    """Convert v1 ``Notification`` models into v2 ``flyte.notify`` notifications.

    v1 email/slack/pagerduty notifications all deliver by emailing a recipient list
    (slack/pagerduty use their email gateways), so each maps to a v2 ``Email``.
    """
    v2_notifications = []
    for n in notifications or []:
        phases = tuple(_PHASE_V1_TO_V2[p] for p in n.phases if p in _PHASE_V1_TO_V2)
        if not phases:
            continue
        for delivery in (n.email, n.slack, n.pager_duty):
            if delivery and delivery.recipients_email:
                v2_notifications.append(Email(on_phase=phases, recipients=tuple(delivery.recipients_email)))
    return tuple(v2_notifications) or None


def merge_inputs(
    default_inputs: Optional[Dict[str, Any]] = None,
    fixed_inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Merge *default_inputs* and *fixed_inputs* into a single dictionary.

    Fixed inputs take precedence over default inputs when both are provided.
    Returns an empty dict when neither is supplied.
    """
    if default_inputs is None and fixed_inputs is None:
        return {}
    if fixed_inputs is None:
        return default_inputs  # type: ignore[return-value]
    if default_inputs is None:
        return fixed_inputs
    return {**default_inputs, **fixed_inputs}


# v1 fixed-rate units expressed in minutes, which is the only unit v2 FixedRate takes.
_FIXED_RATE_UNIT_MINUTES = {
    _schedule_model.Schedule.FixedRateUnit.MINUTE: 1,
    _schedule_model.Schedule.FixedRateUnit.HOUR: 60,
    _schedule_model.Schedule.FixedRateUnit.DAY: 24 * 60,
}


def _resolve_automation(schedule: _schedule_model.Schedule) -> Union[Cron, FixedRate]:
    """Determine the v2 automation type from a v1 schedule model.

    Checks for a fixed-rate schedule first, then a cron expression, and
    finally a cron schedule object.

    Raises:
        ValueError: If the schedule type is not recognised.
    """
    if schedule.rate:
        # v2 FixedRate is always expressed in minutes; v1 carries a (value, unit) pair, so
        # passing the value straight through turns timedelta(hours=4) into 4 minutes.
        return FixedRate(schedule.rate.value * _FIXED_RATE_UNIT_MINUTES[schedule.rate.unit])
    if schedule.cron_expression:
        return Cron(schedule.cron_expression)
    if schedule.cron_schedule.schedule:
        return Cron(schedule.cron_schedule.schedule)
    raise ValueError(f"Unsupported schedule type: {schedule}")


def schedule_to_trigger(
    name: str,
    schedule: Optional[_schedule_model.Schedule] = None,
    default_inputs: Optional[Dict[str, Any]] = None,
    fixed_inputs: Optional[Dict[str, Any]] = None,
    overwrite_cache: Optional[bool] = None,
    auto_activate: bool = False,
    labels: Optional[_common_models.Labels] = None,
    annotations: Optional[_common_models.Annotations] = None,
    notifications: Optional[List[_common_models.Notification]] = None,
) -> Optional[Trigger]:
    """Convert a v1 ``Schedule`` into a v2 ``Trigger``.

    Returns ``None`` when no *schedule* is provided, allowing callers to
    skip trigger attachment for launch plans without schedules.
    """
    if schedule is None:
        return None

    return Trigger(
        name=name,
        automation=_resolve_automation(schedule),
        inputs=merge_inputs(default_inputs, fixed_inputs),
        overwrite_cache=overwrite_cache if overwrite_cache is not None else False,
        auto_activate=auto_activate,
        labels=dict(labels.values.items()) if labels else None,
        annotations=dict(annotations.values.items()) if annotations else None,
        notifications=_translate_notifications(notifications),
    )


class LaunchPlanTransformer:
    """Drop-in replacement for ``flytekit.LaunchPlan``.

    Translates v1 ``LaunchPlan.create()`` and ``LaunchPlan.get_or_create()``
    calls into v2 ``Trigger`` objects attached to the parent
    ``TaskEnvironment``.
    """

    @classmethod
    def create(
        cls,
        name: str,
        workflow: AsyncFunctionTaskTemplate,
        default_inputs: Optional[Dict[str, Any]] = None,
        fixed_inputs: Optional[Dict[str, Any]] = None,
        schedule: Optional[_schedule_model.Schedule] = None,
        notifications: Optional[List[_common_models.Notification]] = None,
        labels: Optional[_common_models.Labels] = None,
        annotations: Optional[_common_models.Annotations] = None,
        overwrite_cache: Optional[bool] = None,
        auto_activate: bool = False,
        **kwargs: Any,
    ) -> TaskEnvironment:
        """Create a v2 trigger from v1 launch plan parameters.

        If a trigger with the same *name* already exists on the task template,
        this is a no-op (idempotent).
        """
        dropped = sorted(k for k, v in kwargs.items() if v is not None)
        if dropped:
            logger.warning(f"LaunchPlan args not supported by flyte-migrate and ignored: {dropped}")

        parent_env = parent_env_for(workflow.func.__module__)
        task_name = parent_env.name + "." + workflow.func.__name__
        if task_name not in parent_env._tasks:
            return parent_env

        task_template = parent_env._tasks[task_name]

        # Skip if a trigger with this name already exists (idempotent).
        existing_triggers = getattr(task_template, "triggers", ())
        for t in existing_triggers:
            if t.name == name:
                return parent_env

        trigger = schedule_to_trigger(
            name=name,
            schedule=schedule,
            default_inputs=default_inputs,
            fixed_inputs=fixed_inputs,
            overwrite_cache=overwrite_cache,
            auto_activate=auto_activate,
            labels=labels,
            annotations=annotations,
            notifications=notifications,
        )
        if trigger is not None and hasattr(task_template, "triggers"):
            task_template.triggers += (trigger,)

        return parent_env

    @classmethod
    def get_or_create(
        cls,
        workflow: Optional[AsyncFunctionTaskTemplate] = None,
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> TaskEnvironment:
        """Alias for ``create`` matching v1's argument order.

        v1's ``get_or_create(workflow, name=None, ...)`` takes the workflow first and
        defaults the name to the workflow's own name; ``create(name, workflow, ...)``
        is the other way round.  Support both calling conventions.
        """
        if workflow is None:
            workflow = kwargs.pop("workflow")
        return cls.create(name or workflow.func.__name__, workflow, **kwargs)


flytekit.LaunchPlan = LaunchPlanTransformer
