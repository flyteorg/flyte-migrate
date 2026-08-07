"""Task resolver that activates the flyte-migrate shim before importing user code.

Set as ``task_resolver`` on every shimmed ``TaskTemplate`` so remote pods (the
v1→v2 upgrade bootstrap's root action and all child actions) import
:mod:`flyte_migrate` — patching flytekit's namespace — before the user's v1
module is loaded. v2's ``DefaultTaskResolver`` would import the user file with
vanilla flytekit and find v1 objects instead of v2 ``TaskTemplate``s.
"""

import importlib
from pathlib import Path
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from flyte._task import TaskTemplate


class ShimTaskResolver:
    """``DefaultTaskResolver`` clone whose load path applies the shim first."""

    @property
    def import_path(self) -> str:
        return "flyte_migrate._resolver.ShimTaskResolver"

    def load_task(self, loader_args: List[str]) -> "TaskTemplate":
        import flyte_migrate  # noqa: F401  (patches flytekit before the user module loads)

        _, task_module, _, task_name, *_ = loader_args
        module = importlib.import_module(task_module)
        return getattr(module, task_name)

    def loader_args(self, task: "TaskTemplate", root_dir: Path) -> List[str]:
        from flyte._internal.resolvers._task_module import extract_task_module

        name, module = extract_task_module(task, root_dir)
        return ["mod", module, "instance", name]
