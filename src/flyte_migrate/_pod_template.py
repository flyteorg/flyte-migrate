"""Transforms v1 flytekit.PodTemplate into v2 flyte.PodTemplate.

The wrapper preserves pod_spec, primary_container_name, labels, and annotations
from the v1 template.
"""

from typing import Optional

import flyte
import flytekit


def _transform_pod_template_v1_to_v2(pod_template: flytekit.PodTemplate) -> Optional[flyte.PodTemplate]:
    """Convert a v1 ``flytekit.PodTemplate`` to a v2 ``flyte.PodTemplate``.

    Returns ``None`` when *pod_template* is falsy (e.g. ``None``).
    """
    if not pod_template:
        return None
    return flyte.PodTemplate(
        pod_spec=pod_template.pod_spec,
        primary_container_name=pod_template.primary_container_name,
        labels=pod_template.labels,
        annotations=pod_template.annotations,
    )
