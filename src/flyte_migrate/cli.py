"""``pyflyte-migrate`` — run and register v1 flytekit workflows on a Flyte v2 cluster.

Mirrors the ``pyflyte`` UX so migrating users keep their muscle memory:

- ``pyflyte-migrate run wf.py my_wf --name=x`` runs locally (pyflyte semantics),
  ``--remote`` targets the v2 cluster.
- ``pyflyte-migrate register wf.py`` deploys the shimmed workflows/tasks.

Importing this module imports :mod:`flyte_migrate`, which patches flytekit's
namespace *before* any user file is loaded — so files driven by this CLI do not
need the ``import flyte_migrate`` line.

Built on the v2 CLI machinery (``flyte.cli._run``/``_common``): shimmed
``@workflow``/``@task`` objects are v2 ``TaskTemplate`` instances in the user
module's globals, so v2's file/task discovery and input-to-option conversion
work unchanged. Those modules are private to the ``flyte`` SDK, so all imports
of them are concentrated here and ``pyproject.toml`` bounds the ``flyte``
version.
"""

import functools
import importlib.metadata
import importlib.util
import logging
import sys
from pathlib import Path
from typing import List, Tuple, get_args

import flyte
import rich_click as click
from flyte._code_bundle._utils import CopyFiles
from flyte.cli import _common as common
from flyte.cli._run import RunArguments, RunTaskCommand, TaskFiles, TaskPerFileGroup

import flyte_migrate  # noqa: F401  (patches flytekit before any user file is loaded)
from flyte_migrate._workflow import parent_env

try:
    _VERSION = importlib.metadata.version("flyte-migrate")
except importlib.metadata.PackageNotFoundError:
    _VERSION = "unknown"

_LOG_LEVELS = (None, logging.WARNING, logging.INFO, logging.DEBUG)

# v1 `--copy` values -> v2 copy_style
_COPY_TO_V2 = {"all": "all", "auto": "loaded_modules", "none": "none"}


REMOTE_OPTION = click.Option(
    ["-r", "--remote"],
    is_flag=True,
    default=False,
    help="Run on the Flyte v2 cluster instead of locally.",
)

IMAGE_OPTION = click.Option(
    ["-i", "--image", "image"],
    type=str,
    multiple=True,
    help="Image to use. Format: imagename=imageuri (name optional). Can be specified multiple times.",
)

RAW_DATA_OPTION = click.Option(
    ["--raw-data-path", "--raw-output-data-prefix", "--raw-data-prefix", "raw_data_path"],
    type=str,
    default=None,
    help="Prefix used to store offloaded data (FlyteFile, FlyteDirectory, dataframes). e.g. s3://bucket/",
)

# v1 pyflyte run flags that map onto v2 with_runcontext parameters.
_RUN_V1_OPTIONS = [
    click.Option(["--wait", "--wait-execution", "wait"], is_flag=True, default=False, help="Alias for --follow."),
    click.Option(
        ["--copy", "copy"],
        type=click.Choice(["all", "auto"]),
        default=None,
        help="v1-style alias for --copy-style ('auto' maps to loaded_modules).",
    ),
    click.Option(["--copy-all", "copy_all"], is_flag=True, default=False, help="[Deprecated] Same as --copy all."),
    click.Option(
        ["--envvars", "--env", "envvars"],
        type=str,
        multiple=True,
        callback=common.key_value_callback,
        help="Environment variables to set in the container, of the format ENV_NAME=ENV_VALUE.",
    ),
    click.Option(
        ["--labels", "--label", "labels"],
        type=str,
        multiple=True,
        callback=common.key_value_callback,
        help="Labels to attach to the execution, of the format label_key=label_value.",
    ),
    click.Option(
        ["--annotations", "--annotation", "annotations"],
        type=str,
        multiple=True,
        callback=common.key_value_callback,
        help="Annotations to attach to the execution, of the format key=value.",
    ),
    click.Option(
        ["--overwrite-cache"], is_flag=True, default=False, help="Whether to overwrite the cache if it already exists."
    ),
    click.Option(
        ["--interruptible"],
        type=bool,
        default=None,
        help="Force the execution to run with interruptible true/false. Defaults to the task's own setting.",
    ),
]

# v1 pyflyte run flags with no v2 equivalent — accepted so v1 scripts keep parsing, but ignored with a warning.
_RUN_IGNORED_OPTIONS = [
    click.Option(["--destination-dir", "destination_dir"], type=str, default=None, help="Ignored on v2."),
    click.Option(["--poll-interval", "poll_interval"], type=int, default=None, help="Ignored on v2 (use --follow)."),
    click.Option(["--dump-snippet", "dump_snippet"], is_flag=True, default=False, help="Ignored on v2."),
    click.Option(["--max-parallelism", "max_parallelism"], type=int, default=None, help="Ignored on v2."),
    click.Option(["--disable-notifications", "disable_notifications"], is_flag=True, default=False, help="Ignored."),
    click.Option(["--tags", "--tag", "tags"], type=str, multiple=True, help="Ignored on v2."),
    click.Option(["--limit", "limit"], type=int, default=None, help="Ignored on v2."),
    click.Option(["--cluster-pool", "cluster_pool"], type=str, default=None, help="Ignored on v2."),
    click.Option(
        ["--execution-cluster-label", "--ecl", "execution_cluster_label"], type=str, default=None, help="Ignored."
    ),
]


def _warn_ignored(params: dict, options: List[click.Option]) -> None:
    """Pop v1-only options from parsed params, warning when the user actually set one."""
    for opt in options:
        if params.pop(opt.name, None):
            click.echo(f"Warning: {opt.opts[0]} has no v2 equivalent and is ignored", err=True)


class MigrateRunTaskCommand(RunTaskCommand):
    """RunTaskCommand that forwards v1 execution flags (env vars, labels, cache, ...) to with_runcontext."""

    def __init__(self, *args, run_kwargs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.run_kwargs = run_kwargs or {}

    def invoke(self, ctx: click.Context):
        if not self.run_kwargs:
            return super().invoke(ctx)
        # ponytail: upstream RunTaskCommand hardcodes its with_runcontext kwargs; wrapping the
        # factory for the duration of the call beats copying its 30-line body and drifting.
        original = flyte.with_runcontext
        flyte.with_runcontext = functools.partial(original, **self.run_kwargs)  # type: ignore
        try:
            return super().invoke(ctx)
        finally:
            flyte.with_runcontext = original  # type: ignore


class MigrateTaskPerFileGroup(TaskPerFileGroup):
    """TaskPerFileGroup that threads v1 execution flags through to MigrateRunTaskCommand."""

    def __init__(self, *args, run_kwargs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.run_kwargs = run_kwargs or {}

    def _get_command_for_obj(self, ctx: click.Context, obj_name: str, obj) -> click.Command:
        return MigrateRunTaskCommand(
            obj_name=obj_name,
            obj=obj,
            help=obj.docs.__help__str__() if obj.docs else None,
            run_args=self.run_args,
            run_kwargs=self.run_kwargs,
        )


class MigrateTaskFiles(TaskFiles):
    """v2 ``run`` group with pyflyte semantics: local by default, ``--remote`` for the cluster."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Swap v2's --local for pyflyte's --remote, and replace --image / --raw-data-path
        # with versions carrying the v1 short flag and aliases.
        self.params = [p for p in self.params if p.name not in ("local", "image", "raw_data_path")]
        self.params.extend([REMOTE_OPTION, IMAGE_OPTION, RAW_DATA_OPTION, *_RUN_V1_OPTIONS, *_RUN_IGNORED_OPTIONS])

    def list_commands(self, ctx):
        # Only *.py files and directories — drop v2's deployed-task/python-script pseudo-commands.
        return common.FileGroup.list_commands(self, ctx)

    def get_command(self, ctx, cmd_name):
        p = ctx.params
        # Map pyflyte's --remote flag onto v2's `local` RunArguments field.
        p["local"] = not p.pop("remote", False)
        if p.pop("wait", False):
            p["follow"] = True
        copy = p.pop("copy", None)
        if p.pop("copy_all", False):
            copy = "all"
        if copy:
            p["copy_style"] = _COPY_TO_V2[copy]
        run_kwargs = {}
        for param_name, runcontext_name in (
            ("envvars", "env_vars"),
            ("labels", "labels"),
            ("annotations", "annotations"),
        ):
            value = p.pop(param_name, None)
            if value:
                run_kwargs[runcontext_name] = value
        if p.pop("overwrite_cache", False):
            run_kwargs["overwrite_cache"] = True
        interruptible = p.pop("interruptible", None)
        if interruptible is not None:
            run_kwargs["interruptible"] = interruptible
        _warn_ignored(p, _RUN_IGNORED_OPTIONS)

        fp = Path(cmd_name)
        if fp.is_dir():
            # The parent returns a plain TaskFiles for directories, which would lose the flag mapping.
            return MigrateTaskFiles(directory=fp, help=f"Run `*.py` file inside the {fp} directory")
        if not fp.exists():
            raise click.BadParameter(f"File {cmd_name} does not exist")
        run_args = RunArguments.from_dict(p)
        # Same ctx.obj wiring as the parent's get_command (parameter converters read run_args from it).
        if ctx.obj is not None and hasattr(ctx.obj, "replace"):
            ctx.obj = ctx.obj.replace(run_args=run_args)
        else:
            import flyte.config

            ctx.obj = common.CLIConfig(config=flyte.config.auto(), ctx=ctx, run_args=run_args)
        return MigrateTaskPerFileGroup(
            filename=fp,
            run_args=run_args,
            run_kwargs=run_kwargs,
            name=cmd_name,
            help=f"Run functions decorated with `env.task` in {cmd_name}",
        )


run = MigrateTaskFiles(
    name="run",
    help="""
Run a v1 flytekit workflow or task from a python file, locally by default.

Run-level options go before the file name; workflow inputs go after the workflow name:

```bash
pyflyte-migrate run wf.py my_wf --name=flyte
pyflyte-migrate run --remote -p my-project -d development wf.py my_wf --name=flyte
```
""",
)


def _load_file(path: Path) -> None:
    """Import a python file so the shim registers its workflows/tasks into ``parent_env``."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise click.ClickException(f"Could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    sys.path.append(str(path.parent.absolute()))
    spec.loader.exec_module(module)


def _expand_paths(paths: Tuple[Path, ...]) -> List[Path]:
    files: List[Path] = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(f for f in p.glob("*.py") if not f.name.startswith(("_", "."))))
        else:
            files.append(p)
    return files


class _RegisterCommand(common.InvokeBaseMixin, click.RichCommand):
    """Register command with the v2 CLI's grpc/error handling."""


@click.group(cls=click.RichGroup)
@click.version_option(_VERSION, prog_name="pyflyte-migrate")
@click.option("--endpoint", type=str, default=None, help="The Flyte v2 backend endpoint to use.")
@click.option("--org", type=str, default=None, help="The organization to which this command applies.")
@click.option("-v", "--verbose", count=True, help="Increase verbosity (-v, -vv, -vvv).")
@click.option(
    "-c",
    "--config",
    "config_file",
    type=click.Path(exists=True),
    default=None,
    help="Path to a v2 config file (defaults to the standard flyte config discovery).",
)
@click.pass_context
def main(ctx: click.Context, endpoint: str | None, org: str | None, verbose: int, config_file: str | None):
    """Run v1 flytekit workflows on a Flyte v2 cluster without code changes.

    User files do not need the ``import flyte_migrate`` line when driven by this CLI —
    the shim is applied automatically before your file is loaded.
    """
    import flyte.config as config

    ctx.obj = common.CLIConfig(
        config=config.auto(config_file=config_file),
        ctx=ctx,
        log_level=_LOG_LEVELS[min(verbose, 3)],
        endpoint=endpoint,
        org=org,
    )


# v1 pyflyte register flags with no v2 equivalent — accepted so v1 scripts keep parsing, ignored with a warning.
_REGISTER_IGNORED_OPTIONS = [
    click.Option(["-o", "--output", "output"], type=str, default=None, help="Ignored on v2."),
    click.Option(["-D", "--destination-dir", "destination_dir"], type=str, default=None, help="Ignored on v2."),
    click.Option(["--service-account", "service_account"], type=str, default=None, help="Ignored on v2."),
    click.Option(["--raw-data-prefix", "raw_data_prefix"], type=str, default=None, help="Ignored on v2."),
    click.Option(["--deref-symlinks", "deref_symlinks"], is_flag=True, default=False, help="Ignored on v2."),
    click.Option(
        ["--activate-launchplans", "--activate-launchplan", "activate_launchplans"],
        is_flag=True,
        default=False,
        help="Ignored on v2 (deployed triggers are active by default).",
    ),
    click.Option(["--env", "--envvars", "envvars"], type=str, multiple=True, help="Ignored on v2 for register."),
    click.Option(["--resource-requests", "resource_requests"], type=str, default=None, help="Ignored on v2."),
    click.Option(["--resource-limits", "resource_limits"], type=str, default=None, help="Ignored on v2."),
]


@main.command("register", cls=_RegisterCommand)
@click.option("-p", "--project", type=str, default=None, help="Project to register the workflows under.")
@click.option("-d", "--domain", type=str, default=None, help="Domain to register the workflows under.")
@click.option("-v", "--version", type=str, default=None, help="Version to use; defaults to a content-based version.")
@click.option("-i", "--image", type=str, multiple=True, help="Image to use. Format: imagename=imageuri.")
@click.option("--dry-run", "--dryrun", is_flag=True, default=False, help="Do not actually call the backend service.")
@click.option(
    "--copy-style",
    type=click.Choice(get_args(CopyFiles)),
    default="loaded_modules",
    help="Copy style to use for the code bundle.",
)
@click.option(
    "--copy",
    type=click.Choice(["all", "auto", "none"]),
    default=None,
    help="v1-style alias for --copy-style ('auto' maps to loaded_modules).",
)
@click.option("--non-fast", is_flag=True, default=False, help="[Deprecated] Same as --copy none.")
@click.option("--skip-errors", "--skip-error", is_flag=True, default=False, help="Skip files that fail to load.")
@click.option("--root-dir", type=str, default=None, help="Override the root source directory.")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.pass_context
def register(
    ctx: click.Context,
    project: str | None,
    domain: str | None,
    version: str | None,
    image: Tuple[str, ...],
    dry_run: bool,
    copy_style: CopyFiles,
    copy: str | None,
    non_fast: bool,
    skip_errors: bool,
    root_dir: str | None,
    paths: Tuple[Path, ...],
    **ignored,
):
    """Register (deploy) v1 flytekit workflows from files or directories on the v2 cluster.

    All loaded workflows/tasks share one environment, so function names must be
    unique across the registered files.
    """
    for key, value in ignored.items():
        if value:
            click.echo(f"Warning: --{key.replace('_', '-')} has no v2 equivalent and is ignored", err=True)
    if non_fast:
        copy = "none"
    if copy:
        copy_style = _COPY_TO_V2[copy]  # type: ignore[assignment]
    obj: common.CLIConfig = common.initialize_config(ctx, project, domain, root_dir, tuple(image) or None)
    files = _expand_paths(paths)
    if not files:
        raise click.ClickException("No python files found in the given paths")
    for f in files:
        try:
            _load_file(f)
        except Exception as e:
            if not skip_errors:
                raise
            click.echo(f"Warning: skipping {f}: {e}", err=True)
    with common.cli_status(obj.output_format, "Deploying..."):
        deployment = flyte.deploy(parent_env, dryrun=dry_run, copy_style=copy_style, version=version)
    common.print_output(common.format("Environments", deployment[0].env_repr(), obj.output_format), obj.output_format)
    common.print_output(common.format("Entities", deployment[0].table_repr(), obj.output_format), obj.output_format)


register.params.extend(_REGISTER_IGNORED_OPTIONS)


main.add_command(run)
