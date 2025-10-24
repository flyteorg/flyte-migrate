from typing import List, Optional, Any
from pathlib import Path
import flyte
import flytekit

def _mount_name(m: Any) -> str:
    """Return 'ANY' | 'ENV_VAR' | 'FILE' from v1 mount_requirement."""
    if hasattr(m, "name"):
        return m.name
    s = str(m)
    return s.split(".")[-1].upper()

def _transform_secret_v1_to_v2(secret_requests: Optional[List[flytekit.Secret]]) -> Optional[flyte.SecretRequest]:
    if not secret_requests:
        return None
    out: List[flyte.Secret] = []
    for s in secret_requests:
        grp  = getattr(s, "group", None)
        key  = getattr(s, "key", None)
        env  = getattr(s, "env_var", None)
        mreq = getattr(s, "mount_requirement", None)
        mname = _mount_name(mreq) if mreq is not None else "ANY"
        as_env_var: Optional[str] = None
        mount: Optional[Path] = None
        if mname == "FILE":
            secret_manager = flytekit.current_context().secrets
            mount = secret_manager.get_secrets_file(grp, key)
        elif mname == "ENV_VAR":
            as_env_var = env
        out.append(
            flyte.Secret(
                key=key,
                group=grp,
                as_env_var=as_env_var,
                mount=mount,
            )
        )
    return out
