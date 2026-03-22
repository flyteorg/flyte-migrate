"""Transforms v1 flytekit.ImageSpec into v2 flyte.Image.

The main entry point is :func:`_transform_image_spec_v1_to_v2`, which accepts a
v1 ``ImageSpec``, a raw image string, or an already-converted ``flyte.Image``
and returns a v2 ``flyte.Image``.

The v1-to-v2 plugin package name mapping is defined in :data:`_PACKAGE_V1_TO_V2`.
"""

import re
from functools import cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

import flyte
import flytekit
from flyte._logging import logger

from flyte_migrate._workflow import parent_env

# Mapping of v1 flytekitplugins package names to their v2 flyteplugins equivalents.
_PACKAGE_V1_TO_V2: Dict[str, str] = {
    "flytekitplugins-spark": "flyteplugins-spark",
    "flytekitplugins-ray": "flyteplugins-ray",
    "flytekitplugins-dask": "flyteplugins-dask",
    "flytekitplugins-kfpytorch": "flyteplugins-pytorch",
}


def _parse_python_version(version_str: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parse a dotted version string (e.g. ``"3.11"``) into a ``(major, minor)`` tuple."""
    if not version_str:
        return None
    parts = tuple(map(int, version_str.split(".")))
    return (parts[0], parts[1]) if len(parts) >= 2 else None


def _parse_platform(platform_str: Optional[str]) -> Optional[Tuple[str, ...]]:
    """Parse a comma-separated platform string into a tuple of stripped platform names."""
    if not platform_str:
        return None
    return tuple(p.strip() for p in platform_str.split(","))


_VERSION_SPECIFIER_RE = re.compile(r"([><=!~]+.*)")


def _strip_version_specifier(pkg: str) -> Tuple[str, str]:
    """Split a package string into (name, version_specifier).

    E.g. ``"flytekitplugins-spark==1.16.3"`` -> ``("flytekitplugins-spark", "==1.16.3")``.
    """
    match = _VERSION_SPECIFIER_RE.search(pkg)
    if match:
        return pkg[: match.start()], match.group(0)
    return pkg, ""


def _translate_pip_packages(packages: Optional[List[str]]) -> List[str]:
    """Translate v1 pip package names to v2 equivalents.

    Always includes ``flytekit`` as a base dependency. Plugin package names
    listed in :data:`_PACKAGE_V1_TO_V2` are replaced with their v2 counterparts.
    Version specifiers (e.g. ``==1.16.3``) are stripped before lookup and
    discarded — v2 packages use their own versioning.
    """
    translated = ["flytekit"]
    for pkg in packages or []:
        name, _version = _strip_version_specifier(pkg)
        v2_name = _PACKAGE_V1_TO_V2.get(name)
        if v2_name:
            translated.append(v2_name)
        translated.append(pkg)
    return translated


def _build_pip_secret_mounts(
    pip_secret_mounts: Optional[List[Tuple[str, str]]],
) -> Optional[List[flyte.Secret]]:
    """Convert v1 pip secret mount tuples to v2 ``flyte.Secret`` objects."""
    if not pip_secret_mounts:
        return None
    return [flyte.Secret(key=secret_file, mount=Path(mount_path)) for secret_file, mount_path in pip_secret_mounts]


def _extract_attributes(parent: flytekit.ImageSpec, child: flytekit.ImageSpec) -> None:
    """Merge attributes from a child ImageSpec into a parent ImageSpec.

    This handles the case where a v1 ``base_image`` is itself an ``ImageSpec``,
    requiring its packages, indexes, env vars, etc. to be folded into the parent.
    """
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


def _apply_image_layers(
    image: flyte.Image,
    spec: flytekit.ImageSpec,
    *,
    mirror_to_parent: bool = True,
) -> flyte.Image:
    """Apply package, env, command, and source layers from a v1 ImageSpec to a v2 Image.

    When *mirror_to_parent* is ``True`` (the default), each layer is also applied
    to ``parent_env.image`` so the workflow environment stays in sync with child
    task images.
    """
    # parent_env.image is guaranteed to be a flyte.Image at this point
    # (set in _build_base_image via cast), but mypy can't track this across functions.
    parent_image = cast(flyte.Image, parent_env.image)

    # apt packages
    if spec.apt_packages:
        image = image.with_apt_packages(*spec.apt_packages)
        if mirror_to_parent:
            parent_image = parent_image.with_apt_packages(*spec.apt_packages)

    # pip packages — translate v1 plugin names to v2
    pip_packages = _translate_pip_packages(spec.packages)
    pip_secret_mounts = _build_pip_secret_mounts(spec.pip_secret_mounts)
    pip_kwargs = {
        "index_url": spec.pip_index,
        "extra_index_urls": spec.pip_extra_index_url,
        "extra_args": spec.pip_extra_args,
        "secret_mounts": cast(list[flyte.Secret | str] | None, pip_secret_mounts),
    }
    image = image.with_pip_packages(*pip_packages, **pip_kwargs)
    if mirror_to_parent:
        parent_image = parent_image.with_pip_packages(*pip_packages, **pip_kwargs)

    # env vars
    if spec.env:
        image = image.with_env_vars(spec.env)
        if mirror_to_parent:
            parent_image = parent_image.with_env_vars(spec.env)

    # commands
    if spec.commands:
        image = image.with_commands(*spec.commands)
        if mirror_to_parent:
            parent_image = parent_image.with_commands(*spec.commands)

    # requirements file
    if spec.requirements:
        image = image.with_requirements(spec.requirements)
        if mirror_to_parent:
            parent_image = parent_image.with_requirements(spec.requirements)

    # copy files/folders
    if spec.copy:
        for path_str in spec.copy:
            path = Path(path_str)
            if path.is_dir():
                image = image.with_source_folder(path)
                if mirror_to_parent:
                    parent_image = parent_image.with_source_folder(path)
            else:
                image = image.with_source_file(path)
                if mirror_to_parent:
                    parent_image = parent_image.with_source_file(path)

    # source_root (not compatible with source_copy_mode)
    if spec.source_root:
        path = Path(spec.source_root)
        image = image.with_source_folder(path)
        if mirror_to_parent:
            parent_image = parent_image.with_source_folder(path, copy_contents_only=True)

    # unsupported builders
    if spec.builder in {"envd", "noop"}:
        logger.warning("envd/noop builder not supported in v2, ignoring")

    if mirror_to_parent:
        parent_env.image = parent_image

    return image


def _build_base_image(spec: flytekit.ImageSpec) -> flyte.Image:
    """Create the initial v2 Image from a v1 ImageSpec's base_image, registry, and platform."""
    python_version = _parse_python_version(spec.python_version)
    platform = _parse_platform(spec.platform)

    if isinstance(spec.base_image, flytekit.ImageSpec):
        _extract_attributes(spec, spec.base_image)

    if isinstance(spec.base_image, str):
        image = (
            flyte.Image.from_base(spec.base_image)
            .clone(name=spec.name, python_version=python_version, registry=spec.registry, extendable=True)
            .with_pip_packages("flyte", pre=True)
        )
    else:
        image = flyte.Image.from_debian_base(
            name=spec.name,
            python_version=python_version,
            registry=spec.registry,
            platform=platform,  # type: ignore[arg-type]
        )

    parent_env.image = cast(flyte.Image, parent_env.image).clone(
        name=spec.name, registry=spec.registry, python_version=python_version
    )
    return image


@cache
def _transform_image_spec_v1_to_v2(container_image: flytekit.ImageSpec | flyte.Image | str) -> flyte.Image:
    """Transform a v1 container image specification into a v2 ``flyte.Image``.

    Accepts:
    - ``flytekit.ImageSpec`` — full v1 image spec (the main conversion path)
    - ``str`` — a raw Docker image reference
    - ``flyte.Image`` — already a v2 image, returned as-is
    - ``None`` — returns a default debian-based image

    Note: ``conda_packages`` / ``conda_channels`` are not supported in v2.
    ``cuda`` / ``cudnn`` are handled automatically by the Docker builder.
    """
    if isinstance(container_image, flytekit.ImageSpec):
        image = _build_base_image(container_image)
        image = _apply_image_layers(image, container_image)
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
