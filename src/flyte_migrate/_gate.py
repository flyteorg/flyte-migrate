"""Shim v1 gate nodes (``approve``, ``wait_for_input``, ``sleep``) onto v2 primitives.

In v1 these create gate nodes in the DAG.  In the shimmed world, workflows are plain
Python running inside the parent workflow task, so:

- ``wait_for_input`` / ``approve`` map onto ``flyte.new_condition(...).wait()``, which
  pauses the run until the condition is resolved from the UI or an API call.
- ``sleep`` simply sleeps in the workflow driver container, which is alive for the
  whole run anyway in shimmed mode.
"""

import datetime
import time
from typing import Any, Type, Union

import flyte
import flytekit
from flytekit.exceptions.user import FlyteDisapprovalException


def wait_for_input_shim(name: str, timeout: datetime.timedelta, expected_type: Type) -> Any:
    """Drop-in replacement for ``flytekit.wait_for_input``.

    v2 conditions carry ``bool``/``int``/``float``/``str`` payloads; any other
    *expected_type* raises ``TypeError`` (a v2 limitation — v1 allowed arbitrary types).
    """
    return flyte.new_condition(
        name,
        prompt=f"Provide input '{name}'",
        data_type=expected_type,
        timeout=timeout,
    ).wait()


def approve_shim(upstream_item: Any, name: str, timeout: datetime.timedelta) -> Any:
    """Drop-in replacement for ``flytekit.approve``.

    Pauses the run on a boolean condition; returns *upstream_item* when approved and
    raises ``FlyteDisapprovalException`` (the v1 exception) otherwise.
    """
    approved = flyte.new_condition(
        name,
        prompt=f"Approve '{name}'? Value: {upstream_item!r}",
        data_type=bool,
        timeout=timeout,
    ).wait()
    if not approved:
        raise FlyteDisapprovalException(f"Gate node {name} was not approved")
    return upstream_item


def sleep_shim(duration: Union[datetime.timedelta, int, float]) -> None:
    """Drop-in replacement for ``flytekit.sleep``.

    ponytail: sleeps in the workflow driver container, which is already alive for the
    whole run in shimmed mode; switch to the backend core-sleep plugin task
    (``flyte.extras.Sleep``) if driver-container time ever matters.
    """
    seconds = duration.total_seconds() if isinstance(duration, datetime.timedelta) else float(duration)
    time.sleep(seconds)


flytekit.approve = approve_shim
flytekit.sleep = sleep_shim
flytekit.wait_for_input = wait_for_input_shim
