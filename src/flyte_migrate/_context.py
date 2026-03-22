"""Bridge v1 ``flytekit.ExecutionParameters`` attribute access to the v2 runtime context.

FlyteKit v1 code accesses execution metadata (e.g. ``execution_id``,
``execution_date``) via ``flytekit.current_context()`` which returns an
``ExecutionParameters`` instance.  In v2, the equivalent data lives in
``flyte.ctx().data``.

This module patches ``ExecutionParameters.__getattr__`` so that any
attribute lookup is forwarded to the active v2 context's data dictionary,
allowing v1 code to keep using ``flytekit.current_context().execution_id``
transparently.

Known v1 attributes that are commonly accessed:
    - execution_id
    - execution_date
    - stats
    - logging
    - working_directory
    - raw_output_prefix
"""

from typing import Any

from flyte import ctx
from flytekit import ExecutionParameters


def _get_attrs(self: ExecutionParameters, attr_name: str) -> Any:
    """Dynamically fetch attributes from the current Flyte v2 context.

    This function is monkey-patched onto ``ExecutionParameters.__getattr__``
    so that v1-style attribute access (e.g. ``ctx.execution_id``) is resolved
    from the v2 ``flyte.ctx().data`` dictionary.

    Raises:
        RuntimeError: If no active Flyte context is available (i.e. the code
            is not running inside a Flyte task or workflow execution).
        KeyError: If *attr_name* is not present in the context data.
    """
    current_ctx = ctx()
    if current_ctx is None:
        raise RuntimeError(
            "No active Flyte context found. Make sure you are inside a Flyte task or workflow execution."
        )
    return current_ctx.data[attr_name]


# Bind as a dynamic property so v1 attribute access is forwarded to v2 context.
ExecutionParameters.__getattr__ = _get_attrs
