from functools import cache
from pathlib import Path
from typing import Dict, cast

import flyte
import flytekit
from flyte._logging import logger

from flyte_migrate._workflow import parent_env

_package_v1_to_v2: Dict[str, str] = {
    "flytekitplugins-spark": "flyteplugins-spark",
    "flytekitplugins-ray": "flyteplugins-ray",
    "flytekitplugins-dask": "flyteplugins-dask",
}


def _extract_attributes(parent: flytekit.ImageSpec, child: flytekit.ImageSpec) -> None:
    if child.apt_packages:
        if not parent.apt_packages:
            parent.apt_packages = []
        parent = parent.with_apt_packages(child.apt_packages)
    if child.packages:
        if not parent.packages:
            parent.packages = []
        parent.packages.extend(child.packages)
    if child.pip_index:
        if not parent.pip_index:
            parent.pip_index = child.pip_index
        else:
            if not parent.pip_extra_index_url:
                parent.pip_extra_index_url = []
            parent.pip_extra_index_url.extend(child.pip_index)
    if child.pip_extra_index_url:
        if not parent.pip_extra_index_url:
            parent.pip_extra_index_url = []
        parent.pip_extra_index_url.extend(child.pip_extra_index_url)
    if child.pip_secret_mounts:
        if not parent.pip_secret_mounts:
            parent.pip_secret_mounts = []
        parent.pip_secret_mounts.extend(child.pip_secret_mounts)
    if child.pip_extra_args:
        if not parent.pip_extra_args:
            parent.pip_extra_args = child.pip_extra_args
        else:
            parent.pip_extra_args = parent.pip_extra_args + f" {child.pip_extra_args}"
    if child.env:
        if not parent.env:
            parent.env = {}
        parent.env.update(child.env)
    if child.commands:
        if not parent.commands:
            parent.commands = []
        parent.commands.extend(child.commands)
    if child.requirements:
        if not parent.requirements:
            parent.requirements = child.requirements
        else:
            merged_file = "merged_requirements.txt"
            with (
                open(parent.requirements, "r") as f1,
                open(child.requirements, "r") as f2,
                open(merged_file, "w") as out,
            ):
                out.write(f1.read())
                out.write("\n")
                out.write(f2.read())
            parent.requirements = merged_file
    if child.copy:
        if not parent.copy:
            parent.copy = []
        parent.copy.extend(child.copy)


@cache
def _transform_image_spec_v1_to_v2(container_image: flytekit.ImageSpec | flyte.Image | str) -> flyte.Image:
    # conda_packages, conda_channels -- Not supported in v2
    # cuda, cudnn -- Docker builder automatically adds CUDA paths
    if isinstance(container_image, flytekit.ImageSpec):
        # python version
        if container_image.python_version:
            parts = tuple(map(int, container_image.python_version.split(".")))
            python_version = (parts[0], parts[1]) if len(parts) >= 2 else None
        else:
            python_version = None

        # base_image + registry + platform
        # platform works differently with from_base since an image already existed
        platform = tuple(p.strip() for p in container_image.platform.split(",")) if container_image.platform else None
        if isinstance(container_image.base_image, flytekit.ImageSpec):
            _extract_attributes(container_image, container_image.base_image)
        if isinstance(container_image.base_image, str):
            image = (
                flyte.Image.from_base(container_image.base_image)
                .clone(name=container_image.name, python_version=python_version, registry=container_image.registry)
                .with_pip_packages("flyte", pre=True)
            )
        else:
            image = flyte.Image.from_debian_base(
                name=container_image.name,
                python_version=python_version,
                registry=container_image.registry,
                platform=platform,
            )
        parent_env.image = cast(flyte.Image, parent_env.image).clone(
            name=container_image.name, registry=container_image.registry, python_version=python_version
        )

        # apt packages
        if container_image.apt_packages:
            image = image.with_apt_packages(*container_image.apt_packages)
            parent_env.image = parent_env.image.with_apt_packages(*container_image.apt_packages)

        # pip_packages, pip_index, pip_extra_index_url, pip_extra_args, pip_secret_mounts
        pip_packages = ["flytekit"]
        for pkg in container_image.packages or []:
            if pkg in _package_v1_to_v2:
                pip_packages.append(_package_v1_to_v2[pkg])
            else:
                pip_packages.append(pkg)

        pip_secret_mounts = None
        if container_image.pip_secret_mounts:
            pip_secret_mounts = [
                flyte.Secret(key=secret_file, mount=Path(mount_path))
                for secret_file, mount_path in container_image.pip_secret_mounts
            ]
        image = image.with_pip_packages(
            *pip_packages,
            index_url=container_image.pip_index,
            extra_index_urls=container_image.pip_extra_index_url,
            extra_args=container_image.pip_extra_args,
            secret_mounts=cast(list[flyte.Secret | str] | None, pip_secret_mounts),
        )

        parent_env.image = parent_env.image.with_pip_packages(
            *pip_packages,
            index_url=container_image.pip_index,
            extra_index_urls=container_image.pip_extra_index_url,
            extra_args=container_image.pip_extra_args,
            secret_mounts=cast(list[flyte.Secret | str] | None, pip_secret_mounts),
        )

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

        # copy
        if container_image.copy:
            for path_str in container_image.copy:
                path = Path(path_str)
                if path.is_dir():
                    image = image.with_source_folder(path)
                    parent_env.image = parent_env.image.with_source_folder(path)
                else:
                    image = image.with_source_file(path)
                    parent_env.image = parent_env.image.with_source_file(path)

        # source_root (Not compatible with source_copy_mode)
        if container_image.source_root:
            path = Path(container_image.source_root)
            image = image.with_source_folder(path)
            parent_env.image = parent_env.image.with_source_folder(path, copy_contents_only=True)

        # builder
        if container_image.builder in {"envd", "noop"}:
            logger.warning("envd/noop builder not supported in v2, ignoring")

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
