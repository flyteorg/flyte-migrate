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
from flyte.cli._run import TaskFiles

import flyte_migrate  # noqa: F401  (patches flytekit before any user file is loaded)
from flyte_migrate._workflow import parent_env

try:
    _VERSION = importlib.metadata.version("flyte-migrate")
except importlib.metadata.PackageNotFoundError:
    _VERSION = "unknown"

_LOG_LEVELS = (None, logging.WARNING, logging.INFO, logging.DEBUG)


REMOTE_OPTION = click.Option(
    ["--remote"],
    is_flag=True,
    default=False,
    help="Run on the Flyte v2 cluster instead of locally.",
)


class MigrateTaskFiles(TaskFiles):
    """v2 ``run`` group with pyflyte semantics: local by default, ``--remote`` for the cluster."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params = [p for p in self.params if p.name != "local"]
        self.params.append(REMOTE_OPTION)

    def list_commands(self, ctx):
        # Only *.py files and directories — drop v2's deployed-task/python-script pseudo-commands.
        return common.FileGroup.list_commands(self, ctx)

    def get_command(self, ctx, cmd_name):
        # Map pyflyte's --remote flag onto v2's `local` RunArguments field.
        ctx.params["local"] = not ctx.params.pop("remote", False)
        fp = Path(cmd_name)
        if fp.is_dir():
            # The parent returns a plain TaskFiles for directories, which would lose the flag mapping.
            return MigrateTaskFiles(directory=fp, help=f"Run `*.py` file inside the {fp} directory")
        return super().get_command(ctx, cmd_name)


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


@main.command("register", cls=_RegisterCommand)
@click.option("-p", "--project", type=str, default=None, help="Project to register the workflows under.")
@click.option("-d", "--domain", type=str, default=None, help="Domain to register the workflows under.")
@click.option("--version", type=str, default=None, help="Version to use; defaults to a content-based version.")
@click.option("--dry-run", "--dryrun", is_flag=True, default=False, help="Do not actually call the backend service.")
@click.option(
    "--copy-style",
    type=click.Choice(get_args(CopyFiles)),
    default="loaded_modules",
    help="Copy style to use for the code bundle.",
)
@click.option("--root-dir", type=str, default=None, help="Override the root source directory.")
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.pass_context
def register(
    ctx: click.Context,
    project: str | None,
    domain: str | None,
    version: str | None,
    dry_run: bool,
    copy_style: CopyFiles,
    root_dir: str | None,
    paths: Tuple[Path, ...],
):
    """Register (deploy) v1 flytekit workflows from files or directories on the v2 cluster.

    All loaded workflows/tasks share one environment, so function names must be
    unique across the registered files.
    """
    obj: common.CLIConfig = common.initialize_config(ctx, project, domain, root_dir)
    files = _expand_paths(paths)
    if not files:
        raise click.ClickException("No python files found in the given paths")
    for f in files:
        _load_file(f)
    with common.cli_status(obj.output_format, "Deploying..."):
        deployment = flyte.deploy(parent_env, dryrun=dry_run, copy_style=copy_style, version=version)
    common.print_output(common.format("Environments", deployment[0].env_repr(), obj.output_format), obj.output_format)
    common.print_output(common.format("Entities", deployment[0].table_repr(), obj.output_format), obj.output_format)


main.add_command(run)
