"""Records the local ``sys.path`` on environments at deploy time.

``flyte.run`` stamps the sys.path entries under the root directory into the
``_F_SYS_PATH`` container env var, and the runtime re-adds them before importing the
task module. ``flyte.deploy`` does not do this — it only ever mattered for tasks the
client launches itself.

A v1 ``LaunchPlan`` with a schedule becomes a v2 ``Trigger``, and the platform launches
those from the registered spec with no client involved. Without ``_F_SYS_PATH`` the
container never puts ``./src`` on the path, so every shimmed module dies on its first
line at ``import flyte_migrate`` with ``ModuleNotFoundError`` — flyte_migrate ships in
the code bundle, not as an installed package.

So: wrap ``flyte.deploy`` and stamp the same value ``flyte.run`` would have.
"""

import pathlib
import sys
from typing import Any, Dict, Iterable, List, Optional

import flyte
from flyte._constants import FLYTE_SYS_PATH
from flyte._initialize import get_init_config
from flyte._logging import logger

_original_deploy = flyte.deploy


def _local_sys_path() -> Optional[str]:
    """The ``_F_SYS_PATH`` value for the current init config, or ``None`` if not applicable."""
    cfg = get_init_config()
    if cfg is None or not cfg.sync_local_sys_paths or cfg.root_dir is None:
        return None
    root_dir = pathlib.Path(cfg.root_dir).resolve()
    paths = [f"./{pathlib.Path(p).relative_to(root_dir)}" for p in sys.path if pathlib.Path(p).is_relative_to(root_dir)]
    return ":".join(paths) if paths else None


def _set_sys_path(target: Any, value: str) -> None:
    """Add ``_F_SYS_PATH`` to *target*'s env_vars, leaving an existing value alone."""
    env_vars: Dict[str, str] = dict(getattr(target, "env_vars", None) or {})
    if FLYTE_SYS_PATH not in env_vars:
        env_vars[FLYTE_SYS_PATH] = value
        target.env_vars = env_vars


def _stamp_sys_path(envs: Iterable[Any]) -> None:
    """Set ``_F_SYS_PATH`` on *envs*, their tasks, and everything they depend on."""
    value = _local_sys_path()
    if not value:
        return

    seen: set = set()
    pending: List[Any] = list(envs)
    while pending:
        env = pending.pop()
        if id(env) in seen or not hasattr(env, "env_vars"):
            continue
        seen.add(id(env))

        _set_sys_path(env, value)
        # The container env is serialized from each task template's own env_vars, which were
        # copied off the environment back when the task was decorated — so stamping only the
        # environment here would never reach the registered spec.
        for task in (getattr(env, "_tasks", None) or {}).values():
            _set_sys_path(task, value)

        pending.extend(getattr(env, "depends_on", None) or [])

    logger.debug("Stamped %s=%s on %d environment(s)", FLYTE_SYS_PATH, value, len(seen))


def deploy_shim(*envs: Any, **kwargs: Any) -> Any:
    _stamp_sys_path(envs)
    return _original_deploy(*envs, **kwargs)


async def _deploy_shim_aio(*envs: Any, **kwargs: Any) -> Any:
    _stamp_sys_path(envs)
    return await _original_deploy.aio(*envs, **kwargs)


deploy_shim.aio = _deploy_shim_aio  # type: ignore[attr-defined]
flyte.deploy = deploy_shim  # type: ignore[assignment]
