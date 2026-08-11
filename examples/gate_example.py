"""v1 gate nodes on v2: ``sleep`` runs unattended; ``approve`` pauses the run on a condition.

``sleep_wf`` completes on its own.  ``approval_wf`` creates a v2 condition and waits for a
human to approve it from the UI (or the run fails with a timeout after 30s — which is what
the integration test asserts, since nobody is around to click).
"""

import flyte_migrate  # noqa: F401, I001
import logging
from datetime import timedelta

from flytekit import approve, sleep, task, workflow


@task
def double(x: int) -> int:
    return x * 2


@workflow
def sleep_wf(x: int) -> int:
    y = double(x=x)
    sleep(timedelta(seconds=5))
    return double(x=y)


@workflow
def approval_wf(x: int) -> int:
    y = double(x=x)
    approved = approve(y, "double-check", timeout=timedelta(seconds=30))
    return double(x=approved)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(approval_wf, x=5)
    print(run.name)
    print(run.url)
    run.wait(quiet=False)
