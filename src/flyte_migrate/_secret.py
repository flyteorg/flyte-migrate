"""Transforms v1 flytekit.Secret objects into v2 flyte.Secret equivalents.

The v1 ``MountType.FILE`` maps to the v2 ``mount`` parameter, while
``MountType.ENV_VAR`` (or the default) maps to ``as_env_var``.
"""

from typing import List, Optional, Union

import flyte
import flytekit


def _transform_secret_v1_to_v2(
    secret_requests: Optional[List[flytekit.Secret]],
) -> Optional[List[Union[str, flyte.Secret]]]:
    """Convert a list of v1 secrets to their v2 representations.

    Returns ``None`` when *secret_requests* is empty or ``None``.
    """
    if not secret_requests:
        return None
    return [_convert_single_secret(s) for s in secret_requests]


def _convert_single_secret(secret: flytekit.Secret) -> flyte.Secret:
    """Map a single v1 ``flytekit.Secret`` to a v2 ``flyte.Secret``.

    * ``MountType.FILE`` -> ``mount`` parameter
    * Any other mount type   -> ``as_env_var`` parameter
    """
    is_file_mount = secret.mount_requirement == flytekit.Secret.MountType.FILE
    return flyte.Secret(
        key=secret.key,
        group=secret.group,
        as_env_var=secret.env_var if not is_file_mount else None,
        mount=secret.env_var if is_file_mount else None,
    )
