from typing import List, Optional, Any
from pathlib import Path
import flyte
import flytekit

def _transform_secret_v1_to_v2(secret_requests: Optional[List[flytekit.Secret]]) -> Optional[flyte.SecretRequest]:
    if not secret_requests:
        return None
    out: List[flyte.Secret] = []
    for s in secret_requests:
        out.append(
            flyte.Secret(
                key=s.key,
                group=s.group,
                as_env_var=s.env_var,
                 mount=Path("/etc/flyte/secrets") \
                    if s.mount_requirement == flytekit.Secret.MountType.FILE else None
            )
        )
    return out
