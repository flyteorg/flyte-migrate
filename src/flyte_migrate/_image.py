"""Transforms v1 flytekit.ImageSpec into v2 flyte.Image.

The main entry point is :func:`_transform_image_spec_v1_to_v2`, which accepts a
v1 ``ImageSpec``, a raw image string, or an already-converted ``flyte.Image``
and returns a v2 ``flyte.Image``.

The v1-to-v2 plugin package name mapping is defined in :data:`_PACKAGE_V1_TO_V2`.
"""

import re
import tempfile
from functools import cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

import flyte
import flytekit
from flyte._logging import logger

from flyte_migrate._workflow import _flyte_migrate_requirement

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


# (env name, id(spec)) pairs already folded in, so repeated tasks do not stack layers.
_mirrored: set = set()

_VERSION_SPECIFIER_RE = re.compile(r"([><=!~]+.*)")


def _strip_version_specifier(pkg: str) -> Tuple[str, str]:
    """Split a package string into (name, version_specifier).

    E.g. ``"flytekitplugins-spark==1.16.3"`` -> ``("flytekitplugins-spark", "==1.16.3")``.
    """
    match = _VERSION_SPECIFIER_RE.search(pkg)
    if match:
        return pkg[: match.start()], match.group(0)
    return pkg, ""


def _pin_to_flyte_version(v2_name: str) -> str:
    """Pin a v2 plugin package to the running ``flyte`` version.

    ``flyteplugins-*`` are released in lockstep with ``flyte`` and import its
    internals, so an unpinned plugin resolves to the latest release inside the
    image while ``flyte`` stays at the base image's version — e.g.
    ``ImportError: cannot import name 'system_logger' from 'flyte'``.

    Dev builds of ``flyte`` have no matching release on PyPI, so leave those
    unpinned (mirroring how flyte itself handles dev mode when building images).
    """
    from flyte._version import __version__

    return v2_name if "dev" in __version__ else f"{v2_name}=={__version__}"


def _translate_pip_packages(packages: Optional[List[str]]) -> List[str]:
    """Translate v1 pip package names to v2 equivalents.

    Always includes ``flytekit`` as a base dependency. When a v1 plugin package
    is found in :data:`_PACKAGE_V1_TO_V2`, both the v2 equivalent and the
    original v1 package are included — the v2 package is needed by the runtime
    and the v1 package is needed so remote containers can resolve v1 imports.
    Version specifiers are stripped before lookup but preserved on the original.
    """
    translated = ["flytekit"]
    for pkg in packages or []:
        name, _version = _strip_version_specifier(pkg)
        v2_name = _PACKAGE_V1_TO_V2.get(name)
        if v2_name:
            translated.append(_pin_to_flyte_version(v2_name))
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
            # A temp file, not a fixed name in the cwd: this runs on `import flyte_migrate`,
            # so a relative path drops a stray file in whatever directory the user happens to
            # be in, and the constant name means concurrent merges overwrite each other.
            # v2 only reads and hashes the path, so it does not need to live under root_dir.
            with (
                open(parent.requirements, "r") as f1,
                open(child.requirements, "r") as f2,
                tempfile.NamedTemporaryFile("w", suffix="-requirements.txt", delete=False) as out,
            ):
                out.write(f1.read())
                out.write("\n")
                out.write(f2.read())
            parent.requirements = out.name
    if child.copy:
        if not parent.copy:
            parent.copy = []
        parent.copy.extend(child.copy)


def _apply_image_layers(
    image: flyte.Image,
    spec: flytekit.ImageSpec,
    *,
    mirror: Optional[flyte.TaskEnvironment] = None,
) -> flyte.Image:
    """Apply package, env, command, and source layers from a v1 ImageSpec to a v2 Image.

    When *mirror* is given, each layer is also applied to that environment's image so the
    workflow environment stays in sync with the child task images it drives.
    """
    parent_image = cast(flyte.Image, mirror.image) if mirror is not None else None

    # apt packages
    if spec.apt_packages:
        image = image.with_apt_packages(*spec.apt_packages)
        if parent_image is not None:
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
    if parent_image is not None:
        parent_image = parent_image.with_pip_packages(*pip_packages, **pip_kwargs)

    # env vars
    if spec.env:
        image = image.with_env_vars(spec.env)
        if parent_image is not None:
            parent_image = parent_image.with_env_vars(spec.env)

    # commands
    if spec.commands:
        image = image.with_commands(*spec.commands)
        if parent_image is not None:
            parent_image = parent_image.with_commands(*spec.commands)

    # requirements file
    if spec.requirements:
        image = image.with_requirements(spec.requirements)
        if parent_image is not None:
            parent_image = parent_image.with_requirements(spec.requirements)

    # copy files/folders
    if spec.copy:
        for path_str in spec.copy:
            path = Path(path_str)
            if path.is_dir():
                image = image.with_source_folder(path)
                if parent_image is not None:
                    parent_image = parent_image.with_source_folder(path)
            else:
                image = image.with_source_file(path)
                if parent_image is not None:
                    parent_image = parent_image.with_source_file(path)

    # source_root (not compatible with source_copy_mode)
    if spec.source_root:
        path = Path(spec.source_root)
        image = image.with_source_folder(path)
        if parent_image is not None:
            parent_image = parent_image.with_source_folder(path, copy_contents_only=True)

    # unsupported conda
    if spec.conda_packages:
        logger.warning("conda_packages not supported in v2, ignoring: %s", spec.conda_packages)
    if spec.conda_channels:
        logger.warning("conda_channels not supported in v2, ignoring: %s", spec.conda_channels)

    # unsupported builders
    if spec.builder in {"envd", "noop"}:
        logger.warning("envd/noop builder not supported in v2, ignoring")

    if mirror is not None:
        mirror.image = parent_image

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

    return image


def uses_pod_template(pod_template: object, task_config: object) -> bool:
    """Whether a v1 ``PodTemplate`` gets constructed when this task's module is imported.

    Covers both ``@task(pod_template=...)`` and plugin configs that carry their own, such as
    ``Spark(driver_pod=..., executor_pod=...)`` — the import blows up either way.
    """
    if pod_template is not None:
        return True
    return any(
        getattr(task_config, field, None) is not None for field in ("driver_pod", "executor_pod", "pod_template")
    )


def needs_pip_at_runtime(task_config: object) -> bool:
    """Whether the plugin pip-installs at run time, e.g. a Ray ``runtime_env`` with ``pip``.

    Ray builds a virtualenv for the runtime_env and installs into it; the image's uv-built
    venv has no pip to seed from, so the job dies with "No module named pip".
    """
    runtime_env = getattr(task_config, "runtime_env", None)
    return isinstance(runtime_env, dict) and bool(runtime_env.get("pip"))


def with_kubernetes_client(image: flyte.Image) -> flyte.Image:
    """Add the ``kubernetes`` client, which a v1 ``PodTemplate`` needs at import time.

    ``flytekit.PodTemplate.__post_init__`` does ``from kubernetes.client import V1PodSpec``,
    and both the task container and the parent workflow container re-import the defining
    module — so a task that builds a PodTemplate dies on import unless the client is in the
    image. v1 users get it from the flytekit image; a v1 ImageSpec has to ask for it.

    Idempotent: this is applied per module, so the same image is offered repeatedly and a
    duplicate layer would change the image hash for no reason.
    """
    if any("kubernetes" in (getattr(layer, "packages", None) or ()) for layer in image._layers):
        return image
    return image.with_pip_packages("kubernetes")


def mirror_spec_onto(env: flyte.TaskEnvironment, container_image: object) -> None:
    """Fold a task's v1 ImageSpec into *env*'s image, so the workflow driver matches its tasks.

    Kept out of :func:`_transform_image_spec_v1_to_v2` because that one is cached on the
    spec alone, while the environment to mirror onto differs per defining module.
    """
    if not isinstance(container_image, flytekit.ImageSpec):
        return
    key = (env.name, id(container_image))
    if key in _mirrored:
        return
    _mirrored.add(key)
    base = cast(flyte.Image, env.image).clone(name=container_image.name, registry=container_image.registry)
    # NOTE: python_version is deliberately not carried over. clone() only rewrites the
    # declared version — the base layer stays on the local interpreter's — so a task asking
    # for a different one fails the build with "No interpreter found for Python 3.x".
    # The parent env only runs the workflow driver, so it does not need the task's version.
    env.image = _apply_image_layers(base, container_image)


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
    # Pre-built v2 images are passed through untouched; everything else gets flyte-migrate
    # installed so `import flyte_migrate` resolves inside the container.
    if isinstance(container_image, flytekit.ImageSpec):
        image = _build_base_image(container_image)
        image = _apply_image_layers(image, container_image)
        image = image.with_pip_packages(_flyte_migrate_requirement())
    elif isinstance(container_image, str):
        # from_base images are unnamed and non-extendable by default and would reject pip layers.
        image = (
            flyte.Image.from_base(container_image)
            .clone(name="flyte-migrate-image", extendable=True)
            .with_pip_packages("flyte", _flyte_migrate_requirement())
        )
    elif isinstance(container_image, flyte.Image):
        image = container_image
    elif container_image is None:
        image = flyte.Image.from_debian_base().with_pip_packages("flytekit", _flyte_migrate_requirement())
    else:
        raise ValueError(f"Unsupported container_image type: {type(container_image)}")
    return image
