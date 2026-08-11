"""Task resolver that applies the flyte_migrate shim before loading the user module.

The remote container resolves tasks by importing the user's file (``a0 --resolver ...``).
Files driven by ``pyflyte-migrate`` don't carry the ``import flyte_migrate`` line, so the
default resolver would import raw v1 flytekit and never find the shimmed v2 task. Pointing
``TaskTemplate.task_resolver`` here makes ``a0`` import this module first — and importing
any ``flyte_migrate`` submodule runs the package ``__init__``, which patches flytekit
before the user module loads.
"""

from flyte._internal.resolvers.default import DefaultTaskResolver


class MigrateTaskResolver(DefaultTaskResolver):
    @property
    def import_path(self) -> str:
        return "flyte_migrate._resolver.MigrateTaskResolver"
