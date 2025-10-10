from functools import cache
from pathlib import Path

import flyte
import flytekit

from flyte_migrate._workflow import parent_env


@cache
def _transform_image_spec_v1_to_v2(container_image: flytekit.ImageSpec | flyte.Image | str) -> flyte.Image:
    if isinstance(container_image, flytekit.ImageSpec):
        image = flyte.Image.from_debian_base()
        # Apt packages
        if container_image.apt_packages:
            image = image.with_apt_packages(*container_image.apt_packages)
            parent_env.image = parent_env.image.with_apt_packages(*container_image.apt_packages)
        # Pip packages
        pip_packages = ["flytekit"]
        if container_image.packages:
            pip_packages.extend(container_image.packages)
        image = image.with_pip_packages(*pip_packages)
        parent_env.image = parent_env.image.with_pip_packages(*pip_packages)

    elif isinstance(container_image, str):
        image = flyte.Image.from_base(container_image).with_pip_packages("flyte")
    else:
        image = container_image.with_pip_packages("flytekit")

    return image.with_source_folder(Path(__file__).parent.parent.parent, "./flyte-migrate").with_env_vars({"PYTHONPATH": "./flyte-migrate/src:${PYTHONPATH}"})
