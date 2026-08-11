"""v1 renders a task's deck when the task ends; the shim must guarantee that on v2.

flyte 2.5.18's taskrunner guards its end-of-task flush with a stale ``Context`` — it binds
``ctx = internal_ctx()`` *before* ``with ctx.replace_task_context(tctx)``, so the later
``if ctx.get_report()`` reads the parent's task context, which is ``None`` for a leaf task.
The auto-flush is skipped and anything appended after the last explicit ``Deck.publish()``
never reaches the UI (observed on run u4nfjj9gspl5227ntm69: 3 flushes for 3 publish() calls,
and the trailing append missing from the report).
"""

import asyncio

import flyte.report
import pytest

from flyte_migrate._task import _flush_deck_at_exit


@pytest.fixture
def flushes(monkeypatch):
    """Count flushes without touching real storage.

    ``flyte.report.flush`` is a syncify wrapper: callable *and* carrying an ``.aio``
    coroutine. The stub has to provide both, or the async path silently falls into the
    wrapper's except-and-log branch.
    """
    calls = []

    class _Flush:
        def __call__(self):
            calls.append("sync")

        async def aio(self):
            calls.append("aio")

    monkeypatch.setattr(flyte.report, "flush", _Flush())
    return calls


def test_sync_task_flushes_on_return(flushes):
    wrapped = _flush_deck_at_exit(lambda: "out")

    assert wrapped() == "out"
    assert flushes == ["sync"]


def test_flushes_even_when_the_task_raises(flushes):
    """The trailing deck content is the most useful thing to see on a failure."""

    def boom():
        raise ValueError("task blew up")

    with pytest.raises(ValueError, match="task blew up"):
        _flush_deck_at_exit(boom)()

    assert flushes == ["sync"]


def test_a_failing_flush_does_not_mask_the_task_error(monkeypatch):
    def exploding_flush():
        raise RuntimeError("storage unreachable")

    monkeypatch.setattr(flyte.report, "flush", exploding_flush)

    def boom():
        raise ValueError("task blew up")

    # The task's own exception must survive, not be replaced by the flush failure.
    with pytest.raises(ValueError, match="task blew up"):
        _flush_deck_at_exit(boom)()


def test_async_task_flushes_on_return(flushes):
    async def work():
        return "out"

    wrapped = _flush_deck_at_exit(work)
    assert asyncio.iscoroutinefunction(wrapped)
    assert asyncio.run(wrapped()) == "out"
    assert flushes == ["aio"]


def test_signature_is_preserved():
    """v2 introspects the task signature to build its interface."""
    import inspect

    def typed(name: str, count: int = 3) -> str:
        return name * count

    wrapped = _flush_deck_at_exit(typed)
    assert inspect.signature(wrapped) == inspect.signature(typed)
    assert wrapped.__name__ == "typed"
