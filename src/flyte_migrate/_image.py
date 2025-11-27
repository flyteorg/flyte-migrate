import re
from functools import cache
from pathlib import Path
from typing import Dict

import flyte
import flytekit

from flyte_migrate._workflow import parent_env

_package_v1_to_v2: Dict[str, str] = {
    "flytekitplugins-spark": "flyteplugins-spark",
    "flytekitplugins-ray": "flyteplugins-ray",
    "flytekitplugins-dask": "flyteplugins-dask",
    "flytekitplugins-kfpytorch": "flyteplugins-pytorch",
}


@cache
def _transform_image_spec_v1_to_v2(container_image: flytekit.ImageSpec | flyte.Image | str) -> flyte.Image:
    if isinstance(container_image, flytekit.ImageSpec):
        if container_image.python_version:
            python_version = tuple(map(int, container_image.python_version.split(".")))
        else:
            python_version = None
        if container_image.base_image:
            image = (
                flyte.Image.from_base(container_image.base_image)
                .clone(name=container_image.name, python_version=python_version)
                .with_pip_packages("flyte", pre=True)
            )
        else:
            image = flyte.Image.from_debian_base(name=container_image.name, python_version=python_version)

        # Apt packages
        if container_image.apt_packages:
            image = image.with_apt_packages(*container_image.apt_packages)
            parent_env.image = parent_env.image.with_apt_packages(*container_image.apt_packages)
        # Pip packages
        pip_packages = ["flytekit"]
        for pkg in container_image.packages:
            pip_packages.append(pkg)
            pkg_name = re.split(r"[<>=!~]", pkg)[0].strip()
            if pkg_name in _package_v1_to_v2:
                pip_packages.append(_package_v1_to_v2[pkg_name])
        image = image.with_pip_packages(*pip_packages)
        parent_env.image = parent_env.image.with_pip_packages(*pip_packages)

    elif isinstance(container_image, str):
        image = flyte.Image.from_base(container_image).with_pip_packages("flyte")
    elif isinstance(container_image, flyte.Image):
        image = container_image
    elif container_image is None:
        image = flyte.Image.from_debian_base().with_pip_packages("flytekit")
    else:
        raise ValueError(f"Unsupported container_image type: {type(container_image)}")

    # TODO: Install flyte-migrate in non-editable mode
    return image
