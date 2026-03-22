import flyte_migrate  # noqa: F401, I001
import logging

from flytekit import ImageSpec, task, workflow

# 1. Default ImageSpec with packages, apt_packages, env, and commands
full_image = ImageSpec(
    packages=["pandas", "scikit-learn"],
    apt_packages=["git", "curl"],
    env={"APP_ENV": "production", "LOG_LEVEL": "info"},
    commands=["mkdir -p /workspace/models"],
)


# 2. ImageSpec with python_version and custom name
versioned_image = ImageSpec(
    name="custom-image",
    packages=["numpy"],
    python_version="3.11",
)


# 3. Nested ImageSpec (base_image is ImageSpec) — child attributes merged into parent
nested_image = ImageSpec(
    packages=["pandas"],
    env={"OUTER": "true"},
    base_image=ImageSpec(
        packages=["numpy"],
        apt_packages=["git"],
        env={"INNER": "true"},
    ),
)


@task(container_image=full_image)
def full_task() -> str:
    import os

    return f"full_image: APP_ENV={os.environ.get('APP_ENV', 'unset')}"


@task(container_image=versioned_image)
def versioned_task() -> str:
    import sys

    return f"versioned_image: python {sys.version}"


@task(container_image=nested_image)
def nested_task() -> str:
    import os

    inner = os.environ.get("INNER", "unset")
    outer = os.environ.get("OUTER", "unset")
    return f"nested_image: INNER={inner}, OUTER={outer}"


@workflow
def image_comprehensive_wf() -> list[str]:
    r0 = full_task()
    r1 = versioned_task()
    r2 = nested_task()
    return [r0, r1, r2]


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(image_comprehensive_wf)
    print(run.name)
    print(run.url)
