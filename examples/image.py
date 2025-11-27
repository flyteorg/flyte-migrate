import flyte_migrate
import flyte
import logging
import os
from flytekit import task, ImageSpec
from flyte_migrate._image import _transform_image_spec_v1_to_v2, _extract_attributes
from flyte_migrate._workflow import parent_env

image_spec = _transform_image_spec_v1_to_v2(
    ImageSpec(
        packages=["pandas"],
        source_root="/Users/john/projects/my-flask-app",
        registry="strawberry_banana",
        env={"API_URL": "https://api.example.com"},
        pip_index="https://internal-pypi.mycompany.com/simple",
        pip_extra_index_url=["https://pypi.org/simple"],
        pip_secret_mounts = [("path/in/container", "path/on/host"),("another/container/path", "another/host/path")],
        commands=["mkdir -p /workspace/models"],
        requirements="requirements.txt",
        copy=["config.yaml"],
        builder="envd",
        base_image=ImageSpec(packages=["hello"]),
    ))

@task(container_image=image_spec)
def my_task():
    print(f"Image Type: {type(image_spec)}")

print(image_spec)
print(parent_env.image)

if __name__ == "__main__":

    import flyte
    
    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(my_task)
    print(run.name)
    print(run.url)
