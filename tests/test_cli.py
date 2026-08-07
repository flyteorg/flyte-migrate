"""Tests for the ``pyflyte-migrate`` CLI."""

import importlib.metadata
import os
from types import SimpleNamespace

import flyte
import flytekit
import pytest
from click.testing import CliRunner

from flyte_migrate._task import task_shim
from flyte_migrate._workflow import parent_env
from flyte_migrate.cli import main

# Deliberately has no `import flyte_migrate` line — proves the CLI applies the shim itself.
WF_TEMPLATE = """\
from flytekit import task, workflow


@task
def {task_name}(x: int) -> int:
    return x * 2


@workflow
def {wf_name}(x: int) -> int:
    return {task_name}(x=x)
"""


@pytest.fixture
def runner(monkeypatch, tmp_path):
    """CliRunner in a tmp cwd with a fake v2 config; defuses the v2 CLI's os._exit(0)."""
    # The v2 CLI machinery hard-exits via os._exit(0) on success to avoid grpc channel
    # teardown hangs; that would kill pytest, so make it a no-op.
    monkeypatch.setattr(os, "_exit", lambda code: None)
    monkeypatch.delenv("FLYTE_API_KEY", raising=False)
    # Run files must live under cwd; ./config.yaml is first in the config search order.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("admin:\n  endpoint: dns:///fake.example.com\n  insecure: true\n")
    return CliRunner()


def _write_wf(tmp_path, stem: str) -> str:
    # Unique module/function names per test: the shim keys envs by function name and
    # sys.modules caches by file stem.
    (tmp_path / f"{stem}.py").write_text(WF_TEMPLATE.format(task_name=f"{stem}_double", wf_name=f"{stem}_wf"))
    return f"{stem}.py"


def _fake_runcontext(calls):
    def fake(**kwargs):
        calls.append(kwargs)

        async def aio(obj, **params):
            return SimpleNamespace(url="mem://fake", outputs=lambda: None)

        return SimpleNamespace(run=SimpleNamespace(aio=aio))

    return fake


def test_help(runner):
    for args in (["--help"], ["run", "--help"], ["register", "--help"]):
        result = runner.invoke(main, args)
        assert result.exit_code == 0, result.output
    result = runner.invoke(main, ["--help"])
    assert "run" in result.output
    assert "register" in result.output


def test_shim_active_on_import():
    # Importing flyte_migrate.cli (done at module top) must leave flytekit patched.
    assert flytekit.task is task_shim


def test_run_lists_entities(runner, tmp_path):
    filename = _write_wf(tmp_path, "listwf")
    result = runner.invoke(main, ["run", filename, "--help"])
    assert result.exit_code == 0, result.output
    assert "listwf_wf" in result.output


def test_run_local_by_default(runner, monkeypatch, tmp_path):
    filename = _write_wf(tmp_path, "localwf")
    calls = []
    monkeypatch.setattr(flyte, "with_runcontext", _fake_runcontext(calls))
    result = runner.invoke(main, ["run", filename, "localwf_wf", "--x", "3"])
    assert result.exit_code == 0, result.output
    assert calls[0]["mode"] == "local"


def test_run_remote_flag(runner, monkeypatch, tmp_path):
    filename = _write_wf(tmp_path, "remotewf")
    calls = []
    monkeypatch.setattr(flyte, "with_runcontext", _fake_runcontext(calls))
    result = runner.invoke(main, ["run", "--remote", "-p", "proj", "-d", "dev", filename, "remotewf_wf", "--x", "3"])
    assert result.exit_code == 0, result.output
    assert calls[0]["mode"] == "remote"


def test_run_v1_flags_map_to_runcontext(runner, monkeypatch, tmp_path):
    filename = _write_wf(tmp_path, "v1flags")
    calls = []
    monkeypatch.setattr(flyte, "with_runcontext", _fake_runcontext(calls))
    result = runner.invoke(
        main,
        [
            "run",
            "--envvars",
            "A=1",
            "--env",
            "B=2",
            "--labels",
            "team=ml",
            "--annotations",
            "note=x",
            "--overwrite-cache",
            "--interruptible",
            "true",
            "--copy",
            "auto",
            filename,
            "v1flags_wf",
            "--x",
            "3",
        ],
    )
    assert result.exit_code == 0, result.output
    kwargs = calls[0]
    assert kwargs["env_vars"] == {"A": "1", "B": "2"}
    assert kwargs["labels"] == {"team": "ml"}
    assert kwargs["annotations"] == {"note": "x"}
    assert kwargs["overwrite_cache"] is True
    assert kwargs["interruptible"] is True
    assert kwargs["copy_style"] == "loaded_modules"


def test_run_short_remote_flag_and_copy_all(runner, monkeypatch, tmp_path):
    filename = _write_wf(tmp_path, "shortr")
    calls = []
    monkeypatch.setattr(flyte, "with_runcontext", _fake_runcontext(calls))
    result = runner.invoke(
        main, ["run", "-r", "-p", "proj", "-d", "dev", "--copy-all", filename, "shortr_wf", "--x", "1"]
    )
    assert result.exit_code == 0, result.output
    assert calls[0]["mode"] == "remote"
    assert calls[0]["copy_style"] == "all"


def test_run_ignored_v1_flags_warn(runner, monkeypatch, tmp_path):
    filename = _write_wf(tmp_path, "ignwf")
    calls = []
    monkeypatch.setattr(flyte, "with_runcontext", _fake_runcontext(calls))
    result = runner.invoke(
        main, ["run", "--max-parallelism", "5", "--tags", "a", "--wait", filename, "ignwf_wf", "--x", "1"]
    )
    assert result.exit_code == 0, result.output
    assert calls[0]["mode"] == "local"
    combined = result.output + (result.stderr or "")
    assert "--max-parallelism" in combined
    assert "ignored" in combined


def test_run_local_end_to_end(runner, tmp_path):
    filename = _write_wf(tmp_path, "e2ewf")
    result = runner.invoke(main, ["run", filename, "e2ewf_wf", "--x", "4"])
    assert result.exit_code == 0, result.output
    assert "Completed Local Run" in result.output


def test_register_dry_run(runner, monkeypatch, tmp_path):
    filename = _write_wf(tmp_path, "regwf")
    captured = {}

    def fake_deploy(env, **kwargs):
        captured["env"] = env
        captured.update(kwargs)
        return [SimpleNamespace(env_repr=list, table_repr=list)]

    monkeypatch.setattr(flyte, "deploy", fake_deploy)
    result = runner.invoke(main, ["register", "--dry-run", "--version", "v1", filename])
    assert result.exit_code == 0, result.output
    assert captured["env"] is parent_env
    assert captured["dryrun"] is True
    assert captured["version"] == "v1"
    # Loading the file registered its task env into the shim's parent environment.
    assert any("regwf_double" in env.name for env in parent_env.depends_on)


def test_register_directory(runner, monkeypatch, tmp_path):
    subdir = tmp_path / "wfs"
    subdir.mkdir()
    _write_wf(subdir, "rega")
    _write_wf(subdir, "regb")
    deploy_calls = []
    monkeypatch.setattr(
        flyte,
        "deploy",
        lambda env, **kw: deploy_calls.append(env) or [SimpleNamespace(env_repr=list, table_repr=list)],
    )
    result = runner.invoke(main, ["register", "--dry-run", "wfs"])
    assert result.exit_code == 0, result.output
    # One deploy call covers all loaded files via the shared parent env.
    assert deploy_calls == [parent_env]
    names = [env.name for env in parent_env.depends_on]
    assert any("rega_double" in n for n in names)
    assert any("regb_double" in n for n in names)


def test_register_v1_flags(runner, monkeypatch, tmp_path):
    filename = _write_wf(tmp_path, "regv1")
    broken = tmp_path / "broken.py"
    broken.write_text("raise RuntimeError('boom')\n")
    captured = {}

    def fake_deploy(env, **kwargs):
        captured.update(kwargs)
        return [SimpleNamespace(env_repr=list, table_repr=list)]

    monkeypatch.setattr(flyte, "deploy", fake_deploy)
    result = runner.invoke(
        main,
        [
            "register",
            "--dry-run",
            "--copy",
            "none",
            "--skip-errors",
            "-i",
            "myimg=ghcr.io/x/y:1",
            "--service-account",
            "sa",
            "broken.py",
            filename,
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["copy_style"] == "none"
    combined = result.output + (result.stderr or "")
    assert "skipping" in combined  # broken.py skipped, not fatal
    assert "--service-account" in combined  # warned as ignored


def test_register_no_python_files(runner, tmp_path):
    (tmp_path / "empty").mkdir()
    result = runner.invoke(main, ["register", "empty"])
    assert result.exit_code != 0
    assert "No python files" in result.output


def test_run_missing_file(runner):
    result = runner.invoke(main, ["run", "nope.py", "some_wf"])
    assert result.exit_code != 0


def test_version_flag(runner):
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "pyflyte-migrate" in result.output


def test_expand_paths(tmp_path):
    from flyte_migrate.cli import _expand_paths

    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "_private.py").write_text("")
    (tmp_path / ".hidden.py").write_text("")
    files = _expand_paths((tmp_path,))
    assert [f.name for f in files] == ["a.py", "b.py"]
    # Explicit files pass through untouched, even underscore-prefixed ones.
    assert _expand_paths((tmp_path / "_private.py",)) == [tmp_path / "_private.py"]


def test_flyte_migrate_requirement(monkeypatch):
    from flyte_migrate._workflow import _flyte_migrate_requirement

    monkeypatch.setattr(importlib.metadata, "version", lambda name: "1.2.3")
    assert _flyte_migrate_requirement() == "flyte-migrate==1.2.3"

    # FLYTE_MIGRATE_SPEC overrides everything (upgrade flow: same build everywhere).
    monkeypatch.setenv("FLYTE_MIGRATE_SPEC", "git+https://example.com/flyte-migrate@branch")
    assert _flyte_migrate_requirement() == "git+https://example.com/flyte-migrate@branch"
    monkeypatch.delenv("FLYTE_MIGRATE_SPEC")

    # Dev/local versions don't exist on PyPI — fall back to unpinned.
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "0.1.dev3+g1234abc")
    assert _flyte_migrate_requirement() == "flyte-migrate"

    def missing(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)
    assert _flyte_migrate_requirement() == "flyte-migrate"


def test_images_include_flyte_migrate():
    from flyte_migrate._image import _transform_image_spec_v1_to_v2

    image = _transform_image_spec_v1_to_v2("python:3.12-cli-test")
    assert "flyte-migrate" in str(image._layers)

    # Pre-built v2 images pass through untouched.
    v2_image = flyte.Image.from_debian_base()
    assert _transform_image_spec_v1_to_v2(v2_image) is v2_image
