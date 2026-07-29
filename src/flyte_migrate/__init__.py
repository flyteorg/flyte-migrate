"""Flyte v1-to-v2 compatibility shim.

Importing this module patches ``flytekit``'s public namespace so that v1 decorators
and classes (``@task``, ``@workflow``, ``@dynamic``, ``map_task``, ``LaunchPlan``,
``Deck``, etc.) are transparently redirected to their v2 equivalents.  The patching
happens at import time — each sub-module below replaces one or more ``flytekit``
attributes with shimmed versions that translate v1 API calls into v2 calls at runtime.
"""

from flyte_migrate import (  # noqa: F401
    _bigquery,
    _context,
    _deck,
    _dynamic,
    _launchplan,
    _map,
    _pod_template,
    _reference,
    _task,
    _workflow,
)


def deploy():
    """Register every shimmed task/workflow in this process on the cluster.

    Running a workflow does not persist its tasks for lookup — only deployed
    tasks can be resolved by ``@reference_task`` / ``@reference_launch_plan``.
    Call this (after ``flyte.init_from_config()``) in the file that defines the
    tasks you want to reference from elsewhere.
    """
    import flyte

    from flyte_migrate._workflow import parent_env

    return flyte.deploy(parent_env)
