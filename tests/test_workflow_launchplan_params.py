"""Tests for v1 parameter handling in workflow_shim and LaunchPlanTransformer."""

import flytekit
from flytekit.models.common import (
    Annotations,
    EmailNotification,
    Labels,
    Notification,
    PagerDutyNotification,
    SlackNotification,
)
from flytekit.models.core.execution import WorkflowExecutionPhase
from flytekit.models.schedule import Schedule

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._launchplan import LaunchPlanTransformer, _translate_notifications, schedule_to_trigger


class TestWorkflowShimParams:
    def test_v1_only_args_are_ignored_not_raised(self, caplog):
        """v1 @workflow args with no v2 equivalent must not break the decorator."""

        @flytekit.workflow(
            failure_policy=flytekit.WorkflowFailurePolicy.FAIL_AFTER_EXECUTABLE_NODES_COMPLETE,
            docs=flytekit.Documentation(short_description="d"),
            pickle_untyped=True,
        )
        def wf_with_v1_args() -> int:
            return 1

        assert wf_with_v1_args is not None

    def test_interruptible_forwarded(self):
        @flytekit.workflow(interruptible=True)
        def wf_interruptible() -> int:
            return 1

        assert wf_interruptible.interruptible is True


class TestTranslateNotifications:
    def test_none_gives_none(self):
        assert _translate_notifications(None) is None
        assert _translate_notifications([]) is None

    def test_email_notification(self):
        v1 = Notification(
            phases=[WorkflowExecutionPhase.SUCCEEDED, WorkflowExecutionPhase.FAILED],
            email=EmailNotification(recipients_email=["a@b.co"]),
        )
        (v2,) = _translate_notifications([v1])
        assert v2.recipients == ("a@b.co",)
        assert set(v2.on_phase) == {"succeeded", "failed"}

    def test_slack_and_pagerduty_map_to_email_recipients(self):
        """v1 delivers slack/pagerduty notifications via email gateways — keep the recipients."""
        v1 = Notification(
            phases=[WorkflowExecutionPhase.TIMED_OUT],
            slack=SlackNotification(recipients_email=["s@b.co"]),
            pager_duty=PagerDutyNotification(recipients_email=["p@b.co"]),
        )
        v2 = _translate_notifications([v1])
        assert {n.recipients[0] for n in v2} == {"s@b.co", "p@b.co"}
        assert all(n.on_phase == ("timed_out",) for n in v2)

    def test_non_terminal_phases_skipped(self):
        v1 = Notification(
            phases=[WorkflowExecutionPhase.RUNNING],
            email=EmailNotification(recipients_email=["a@b.co"]),
        )
        assert _translate_notifications([v1]) is None


class TestScheduleToTrigger:
    def test_labels_annotations_notifications_forwarded(self):
        trigger = schedule_to_trigger(
            name="t",
            schedule=Schedule("s", cron_expression="0 * * * *"),
            labels=Labels({"team": "ml"}),
            annotations=Annotations({"owner": "kevin"}),
            notifications=[
                Notification(
                    phases=[WorkflowExecutionPhase.FAILED],
                    email=EmailNotification(recipients_email=["a@b.co"]),
                )
            ],
        )
        assert trigger.labels == {"team": "ml"}
        assert trigger.annotations == {"owner": "kevin"}
        assert trigger.notifications[0].recipients == ("a@b.co",)


class TestGetOrCreateCallingConventions:
    def test_v1_positional_workflow_first(self):
        """v1 code calls LaunchPlan.get_or_create(wf) with no name."""

        @flytekit.workflow
        def lp_wf() -> int:
            return 1

        env = LaunchPlanTransformer.get_or_create(lp_wf)
        assert env is not None

    def test_keyword_convention_still_works(self):
        @flytekit.workflow
        def lp_wf_kw() -> int:
            return 1

        env = LaunchPlanTransformer.get_or_create(workflow=lp_wf_kw, name="my-lp")
        assert env is not None
