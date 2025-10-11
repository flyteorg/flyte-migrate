from typing import List, Optional

import flyte
import flytekit


def _transform_secret_v1_to_v2(secret_requests: Optional[List[flytekit.Secret]]) -> Optional[flyte.SecretRequest]:
    return None
