"""``_context.py`` bridges v1 ``current_context()`` reads to the v2 runtime.

The bridge has to replace ``ExecutionParameters``' *properties*, not its ``__getattr__``.
``__getattr__`` is only a fallback — Python consults it once normal lookup has raised
``AttributeError`` — and every attribute v1 code reads is a real ``@property``, so a
``__getattr__``-based bridge never runs at all.  It also never fails: flytekit's
``FlyteContextManager.initialize()`` pre-builds a local-run safety net (``local/local/local``
ids, local temp paths) and the properties return *that* on a real cluster, silently.

``TestPropertiesAreWhyTheBridgeMustOverrideThem`` pins that constraint so the approach can't
regress. The rest asserts the values actually come from v2.
"""

import datetime

import flyte
import flytekit
import pytest
from flyte._context import internal_ctx
from flyte._logging import logger as v2_logger
from flyte.models import ActionID, RawDataPath, TaskContext
from flytekit.core.context_manager import ExecutionParameters

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate import _context

# Attributes v1 code reads off current_context().
V1_CONTEXT_ATTRS = [
    "execution_id",
    "execution_date",
    "stats",
    "logging",
    "working_directory",
    "raw_output_prefix",
    "secrets",
    "checkpoint",
    "task_id",
]

V2_ACTION = ActionID(name="a0", run_name="run-abc", project="proj", domain="dev", org="org")
V2_RAW_PATH = "s3://bucket/raw"
V2_VERSION = "v-test"


@pytest.fixture
def v2_task_context():
    """Install a fully-populated v2 ``TaskContext``, as the runtime does inside a task."""
    tctx = TaskContext(
        action=V2_ACTION,
        version=V2_VERSION,
        raw_data_path=RawDataPath(path=V2_RAW_PATH),
        output_path="s3://bucket/out",
        run_base_dir="s3://bucket/run",
        report=None,
    )
    with internal_ctx().replace_task_context(tctx):
        yield tctx


@pytest.fixture(autouse=True)
def reset_warn_once():
    """``_warn_once`` dedupes for the process lifetime; per-test isolation needs it cleared."""
    _context._warned.clear()


# ---------------------------------------------------------------------------
# Why the bridge overrides properties rather than __getattr__
# ---------------------------------------------------------------------------


class TestPropertiesAreWhyTheBridgeMustOverrideThem:
    @pytest.mark.parametrize("attr", V1_CONTEXT_ATTRS)
    def test_every_v1_attribute_is_a_class_level_property(self, attr):
        """A property is found by ``__getattribute__``, so ``__getattr__`` is never consulted —
        which is what makes a ``__getattr__``-only bridge a no-op."""
        assert isinstance(getattr(ExecutionParameters, attr, None), property)

    def test_getattr_is_reached_only_for_names_with_no_property(self, monkeypatch, v2_task_context):
        calls = []
        monkeypatch.setattr(ExecutionParameters, "__getattr__", lambda self, name: calls.append(name))

        ctx = flytekit.current_context()
        for attr in V1_CONTEXT_ATTRS:
            try:
                getattr(ctx, attr)
            except Exception:
                pass  # whether the property succeeds is beside the point
        assert calls == []

        ctx.spark_session
        assert calls == ["spark_session"]


# ---------------------------------------------------------------------------
# Values that come from v2
# ---------------------------------------------------------------------------


class TestValuesComeFromV2:
    def test_the_v2_context_really_is_populated(self, v2_task_context):
        """Guards the fixture, so the assertions below can't pass for the wrong reason."""
        assert flyte.ctx().action == V2_ACTION
        assert flyte.ctx().raw_data_path.path == V2_RAW_PATH

    def test_execution_id_comes_from_the_v2_action(self, v2_task_context):
        execution_id = flytekit.current_context().execution_id

        assert execution_id.project == V2_ACTION.project
        assert execution_id.domain == V2_ACTION.domain

    def test_execution_id_uses_run_name_not_action_name(self, v2_task_context):
        """v1's execution_id identifies the run; ``ActionID.name`` is one task invocation within
        it. Mapping to ``name`` gives every task a different id and breaks its use as a
        run-level correlation / idempotency key — silently, since both are valid strings."""
        assert flytekit.current_context().execution_id.name == V2_ACTION.run_name
        assert V2_ACTION.run_name != V2_ACTION.name  # the fixture keeps them distinct on purpose

    def test_task_id_uses_action_name(self, v2_task_context):
        task_id = flytekit.current_context().task_id

        assert task_id.name == V2_ACTION.name
        assert task_id.version == V2_VERSION

    def test_raw_output_prefix_comes_from_the_v2_raw_data_path(self, v2_task_context):
        """The costliest to get wrong: a local path lets writes succeed and then vanish."""
        assert flytekit.current_context().raw_output_prefix == V2_RAW_PATH

    def test_logging_is_the_v2_logger(self, v2_task_context):
        assert flytekit.current_context().logging is v2_logger

    @pytest.mark.parametrize("attr", ["execution_id", "task_id", "raw_output_prefix"])
    def test_reading_outside_a_task_raises(self, attr):
        """``flyte.ctx()`` returns a falsy-but-not-None sentinel here, so the guard has to be a
        truthiness check; ``is None`` would pass through and explode on ``None``."""
        assert flyte.ctx() is not None and not flyte.ctx()

        with pytest.raises(RuntimeError, match="No active Flyte context"):
            getattr(flytekit.current_context(), attr)


# ---------------------------------------------------------------------------
# Attributes with no v2 source
# ---------------------------------------------------------------------------


class TestNoV2Source:
    def test_stats_warns_and_degrades_to_a_noop(self, v2_task_context, caplog):
        """v2 has no statsd interface. Raising would break workflows that only emit metrics as a
        side note, so the value still works — the warning is what makes the gap visible."""
        with caplog.at_level("WARNING", logger="flyte"):
            stats = flytekit.current_context().stats

        assert stats is not None
        assert "no v2 equivalent" in caplog.text

    def test_execution_date_warns_and_returns_the_v1_value(self, v2_task_context, caplog):
        with caplog.at_level("WARNING", logger="flyte"):
            execution_date = flytekit.current_context().execution_date

        assert isinstance(execution_date, datetime.datetime)
        assert "no v2 equivalent" in caplog.text

    def test_the_warning_is_emitted_once_not_per_read(self, v2_task_context, caplog):
        """These get read inside loops as often as not."""
        with caplog.at_level("WARNING", logger="flyte"):
            for _ in range(5):
                flytekit.current_context().stats

        assert caplog.text.count("no v2 equivalent") == 1

    def test_working_directory_is_left_on_the_v1_local_path(self, v2_task_context):
        """Deliberately not bridged: v1's contract is "a local scratch dir for this task", and a
        local temp dir already satisfies it. Unlike raw_output_prefix, nothing is lost."""
        assert flytekit.current_context().working_directory.startswith("/")

    @pytest.mark.xfail(strict=True, reason="not bridged yet; v2 has ctx().checkpoints")
    def test_checkpoint_comes_from_the_v2_context(self, v2_task_context):
        """Known gap. Unlike the others this one fails loudly — v1's property raises
        NotImplementedError rather than returning a fallback."""
        assert flytekit.current_context().checkpoint is not None


# ---------------------------------------------------------------------------
# Task-type specific context, and the AttributeError protocol
# ---------------------------------------------------------------------------


class TestTaskTypeSpecificContext:
    def test_v1_plugin_attrs_are_found_under_their_upper_cased_key(self, v2_task_context):
        """v1 plugins stash task-type context in ``_attrs`` upper-cased — Spark's session being
        the canonical case — and v1's own ``__getattr__`` upper-cases the lookup to match."""
        ctx = flytekit.current_context()
        ctx._attrs = {"SPARK_SESSION": "<session>"}

        assert ctx.spark_session == "<session>"

    def test_the_v2_data_bag_is_the_fallback(self, v2_task_context):
        v2_task_context.data["custom_key"] = "from v2"

        assert flytekit.current_context().custom_key == "from v2"

    def test_a_missing_attribute_raises_attributeerror(self, v2_task_context):
        with pytest.raises(AttributeError):
            flytekit.current_context().no_such_attribute

    def test_hasattr_is_false_for_a_missing_attribute(self, v2_task_context):
        """v1 code guards optional task-type context with ``hasattr``; anything but
        ``AttributeError`` escapes it and aborts the task instead of returning False."""
        assert hasattr(flytekit.current_context(), "no_such_attribute") is False

    def test_getattr_falls_back_to_its_default(self, v2_task_context):
        assert getattr(flytekit.current_context(), "no_such_attribute", "fallback") == "fallback"

    def test_a_missing_attribute_outside_a_task_also_raises_attributeerror(self):
        """No task context is not the same failure as no such name — this path must not leak the
        sentinel's ``None`` fields as a TypeError."""
        with pytest.raises(AttributeError):
            flytekit.current_context().no_such_attribute
