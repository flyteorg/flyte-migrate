import flyte_migrate  # noqa: F401, I001
import logging
from kubernetes.client import V1Container, V1EnvVar, V1PodSpec
from flytekit import task, workflow, PodTemplate
from flytekit import ImageSpec

custom_image = ImageSpec(packages=["kubernetes"])

pod_template = PodTemplate(
    pod_spec=V1PodSpec(
        containers=[
            V1Container(
                name="primary",
                env=[
                    V1EnvVar(name="hello", value="world"),
                ],
            )
        ],
    ),
    primary_container_name="primary",
    labels={"lKeyA": "lValA"},
    annotations={"aKeyA": "aValA"},
)


@task(pod_template=pod_template, container_image=custom_image)
def say_hello(name: str) -> str:
    import os

    hello = os.getenv("hello", "not_set")
    message = f"{name} {hello}!"
    print(message)
    return message


@workflow
def wf(name: str) -> str:
    return say_hello(name=name)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(wf, name="Hello")
    print(run.name)
    print(run.url)
