"""Flyte v1-to-v2 compatibility shim.

Importing this module patches ``flytekit``'s public namespace so that v1 decorators
and classes (``@task``, ``@workflow``, ``@dynamic``, ``map_task``, ``LaunchPlan``,
``Deck``, etc.) are transparently redirected to their v2 equivalents.  The patching
happens at import time — each sub-module below replaces one or more ``flytekit``
attributes with shimmed versions that translate v1 API calls into v2 calls at runtime.
"""

from flyte_migrate import (  # noqa: F401
    _bigquery,
    _container_task,
    _context,
    _deck,
    _deploy,
    _directory,
    _dynamic,
    _file,
    _gate,
    _launchplan,
    _map,
    _pod_template,
    _reference,
    _structured_dataset,
    _task,
    _workflow,
)
