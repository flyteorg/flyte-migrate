from typing import List, Optional, Union

import flyte
import flytekit


def _transform_secret_v1_to_v2(
    secret_requests: Optional[List[flytekit.Secret]],
) -> Optional[Union[str, flyte.Secret, List[Union[str, flyte.Secret]]]]:
    if not secret_requests:
        return None
    out: List[Union[str, flyte.Secret]] = []
    for s in secret_requests:
        out.append(
            flyte.Secret(
                key=s.key,
                group=s.group,
                as_env_var=s.env_var if s.mount_requirement != flytekit.Secret.MountType.FILE else None,
                mount=s.env_var if s.mount_requirement == flytekit.Secret.MountType.FILE else None,
            )
        )
    return out
