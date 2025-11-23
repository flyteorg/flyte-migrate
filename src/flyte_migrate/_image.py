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
}

@cache
def _transform_image_spec_v1_to_v2(container_image: flytekit.ImageSpec | flyte.Image | str) -> flyte.Image:
    # conda_packages, conda_channels -- Not supported in v2
    # cuda, cudnn -- Docker builder automatically adds CUDA paths
    if isinstance(container_image, flytekit.ImageSpec):
        # python version
        if container_image.python_version:
            python_version = tuple(map(int, container_image.python_version.split(".")))
        else:
            python_version = None
        # base_image + registry + platform
        # platform works differently with from_base since an image already existed
        platform = tuple(p.strip() for p in container_image.platform.split(",")) if container_image.platform else None
        if container_image.base_image:
            image = (
                flyte.Image.from_base(container_image.base_image)
                .clone(name=container_image.name, python_version=python_version, registry=container_image.registry)
                .with_pip_packages("flyte", pre=True)
            )
        else:
            image = flyte.Image.from_debian_base(name=container_image.name, python_version=python_version, \
                                                 registry=container_image.registry, platform=platform)
        parent_env.image = flyte.Image.from_debian_base(platform=platform, registry=container_image.registry)\
            .with_pip_packages("setuptools", "flytekit")

        # apt packages
        if container_image.apt_packages:
            image = image.with_apt_packages(*container_image.apt_packages)
            parent_env.image = parent_env.image.with_apt_packages(*container_image.apt_packages)
    
        # pip_packages, pip_index, pip_extra_index_url, pip_extra_args, pip_secret_mounts
        pip_packages = ["flytekit"]
        for pkg in container_image.packages:
            pip_packages.append(pkg)
            pkg_name = re.split(r"[<>=!~]", pkg)[0].strip()
            if pkg_name in _package_v1_to_v2:
                pip_packages.append(_package_v1_to_v2[pkg_name])
        pip_index = container_image.pip_index if container_image.pip_index else None
        pip_extra_index_url = container_image.pip_extra_index_url if container_image.pip_extra_index_url else None
        pip_extra_args = container_image.pip_extra_args if container_image.pip_extra_args else None
        pip_secret_mounts = container_image.pip_secret_mounts if container_image.pip_secret_mounts else None
        image = image.with_pip_packages(*pip_packages, index_url=pip_index, extra_index_urls=pip_extra_index_url, \
                                        extra_args=pip_extra_args, secret_mounts=pip_secret_mounts)
        parent_env.image = parent_env.image.with_pip_packages(*pip_packages, index_url=pip_index, \
                                                              extra_index_urls=pip_extra_index_url, \
                                                              extra_args=pip_extra_args, \
                                                              secret_mounts=pip_secret_mounts)
        
        # env
        if container_image.env:
            image = image.with_env_vars(container_image.env)
            parent_env.image = parent_env.image.with_env_vars(container_image.env)

        # commands
        if container_image.commands:
            image = image.with_commands(*container_image.commands)
            parent_env.image = parent_env.image.with_commands(*container_image.commands)

        # requirements
        if container_image.requirements:
            image = image.with_requirements(container_image.requirements)
            parent_env.image = parent_env.image.with_requirements(container_image.requirements)

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
