import flyte_migrate  # noqa: F401, I001
import logging

import flyte
from flytekit import ImageSpec, task

from flyte_migrate._image import _transform_image_spec_v1_to_v2

image_spec = _transform_image_spec_v1_to_v2(
    ImageSpec(
        packages=["pandas"],
        env={"API_URL": "https://api.example.com"},
        pip_index="https://pypi.org/simple",
        pip_extra_index_url=["https://pypi.org/simple"],
        commands=["mkdir -p /workspace/models"],
        copy=["pyproject.toml"],
        builder="envd",
        base_image=ImageSpec(packages=["numpy"]),
        # source_root="/your/source/root",
        # registry="your_registry",
        # pip_secret_mounts = [("path/in/container", "path/on/host"),("another/container/path", "another/host/path")],
        # requirements="requirements.txt",
    )
)


@task(container_image=image_spec)
def my_task():
    print(f"Image Type: {type(image_spec)}")


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(my_task)
    print(run.name)
    print(run.url)
