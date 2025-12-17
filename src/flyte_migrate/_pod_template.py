import flyte
import flytekit


def _transform_pod_template_v1_to_v2(pod_template: flytekit.PodTemplate) -> flyte.PodTemplate | None:

    if not pod_template:
        return None
    return flyte.PodTemplate(
        pod_spec=pod_template.pod_spec,
        primary_container_name=pod_template.primary_container_name,
        labels=pod_template.labels,
        annotations=pod_template.annotations,
    )
