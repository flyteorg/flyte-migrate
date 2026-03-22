import flyte_migrate  # noqa: F401, I001
import logging
import os

from flytekit import ImageSpec, PodTemplate, task, workflow
from kubernetes.client import (
    V1Affinity,
    V1Container,
    V1EnvVar,
    V1NodeAffinity,
    V1NodeSelector,
    V1NodeSelectorRequirement,
    V1NodeSelectorTerm,
    V1PodSpec,
    V1ResourceRequirements,
    V1Toleration,
)

custom_image = ImageSpec(packages=["kubernetes"])

# --- PodTemplate with labels and annotations ---
labeled_template = PodTemplate(
    pod_spec=V1PodSpec(containers=[V1Container(name="primary")]),
    primary_container_name="primary",
    labels={"team": "ml-infra", "env": "test", "component": "secret-pod-test"},
    annotations={"owner": "flyte-migrate", "purpose": "comprehensive-testing"},
)


@task(pod_template=labeled_template, container_image=custom_image)
def labeled_task(name: str) -> str:
    """Task with labels and annotations on the pod."""
    return f"labeled: {name}"


# --- PodTemplate with environment variables via pod spec ---
env_template = PodTemplate(
    pod_spec=V1PodSpec(
        containers=[
            V1Container(
                name="primary",
                env=[
                    V1EnvVar(name="MY_APP_ENV", value="production"),
                    V1EnvVar(name="MY_APP_VERSION", value="2.0"),
                ],
            )
        ],
    ),
    primary_container_name="primary",
)


@task(pod_template=env_template, container_image=custom_image)
def env_var_task() -> str:
    """Task that reads environment variables set via pod template."""
    app_env = os.getenv("MY_APP_ENV", "NOT_SET")
    app_ver = os.getenv("MY_APP_VERSION", "NOT_SET")
    result = f"env={app_env}, version={app_ver}"
    print(result)
    return result


# --- PodTemplate with resource limits in pod spec ---
resource_template = PodTemplate(
    pod_spec=V1PodSpec(
        containers=[
            V1Container(
                name="primary",
                resources=V1ResourceRequirements(
                    limits={"cpu": "1", "memory": "512Mi"},
                    requests={"cpu": "500m", "memory": "256Mi"},
                ),
            )
        ],
    ),
    primary_container_name="primary",
)


@task(pod_template=resource_template, container_image=custom_image)
def resource_limit_task() -> str:
    """Task with resource limits set via pod template."""
    return "resource limits applied"


# --- PodTemplate with primary_container_name ---
named_container_template = PodTemplate(
    pod_spec=V1PodSpec(
        containers=[
            V1Container(
                name="my-custom-container",
                env=[V1EnvVar(name="CONTAINER_ID", value="custom")],
            )
        ],
    ),
    primary_container_name="my-custom-container",
)


@task(pod_template=named_container_template, container_image=custom_image)
def named_container_task() -> str:
    """Task with a custom primary_container_name."""
    cid = os.getenv("CONTAINER_ID", "NOT_SET")
    return f"container_id={cid}"


# --- PodTemplate with toleration ---
# NOTE: This requires a node with a matching taint in the cluster.
# If no node has the taint `dedicated=ml:NoSchedule`, this task will
# remain Pending until it times out. Use only on clusters configured
# with the matching taint.
toleration_template = PodTemplate(
    pod_spec=V1PodSpec(
        containers=[V1Container(name="primary")],
        tolerations=[
            V1Toleration(
                key="dedicated",
                operator="Equal",
                value="ml",
                effect="NoSchedule",
            )
        ],
    ),
    primary_container_name="primary",
    labels={"test": "toleration"},
)


@task(pod_template=toleration_template, container_image=custom_image)
def toleration_task() -> str:
    """Task with a toleration. Requires cluster taint: dedicated=ml:NoSchedule."""
    return "toleration applied"


# --- PodTemplate with node affinity ---
# NOTE: This requires nodes labeled with `accelerator=nvidia-tesla-v100`.
# If no matching node exists, this task will remain Pending.
affinity_template = PodTemplate(
    pod_spec=V1PodSpec(
        containers=[V1Container(name="primary")],
        affinity=V1Affinity(
            node_affinity=V1NodeAffinity(
                required_during_scheduling_ignored_during_execution=V1NodeSelector(
                    node_selector_terms=[
                        V1NodeSelectorTerm(
                            match_expressions=[
                                V1NodeSelectorRequirement(
                                    key="accelerator",
                                    operator="In",
                                    values=["nvidia-tesla-v100"],
                                )
                            ]
                        )
                    ]
                )
            )
        ),
    ),
    primary_container_name="primary",
    labels={"test": "affinity"},
)


@task(pod_template=affinity_template, container_image=custom_image)
def affinity_task() -> str:
    """Task with node affinity. Requires node label: accelerator=nvidia-tesla-v100."""
    return "affinity applied"


# --- Workflow using tasks that will work on any cluster ---
@workflow
def pod_template_comprehensive_wf(name: str) -> str:
    a = labeled_task(name=name)
    b = env_var_task()
    c = resource_limit_task()
    d = named_container_task()
    return f"{a}, {b}, {c}, {d}"


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(pod_template_comprehensive_wf, name="Hello")
    print(run.name)
    print(run.url)
