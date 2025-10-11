from flyte import ctx
from flytekit import ExecutionParameters


def _get_attrs(self, attr_name: str):
    """Dynamically fetch attributes from the current Flyte context."""
    current_ctx = ctx()
    if current_ctx is None:
        raise RuntimeError(
            "No active Flyte context found. Make sure you are inside a Flyte task or workflow execution."
        )
    return current_ctx.data[attr_name]


# Bind as a dynamic property
ExecutionParameters.__getattr__ = _get_attrs
