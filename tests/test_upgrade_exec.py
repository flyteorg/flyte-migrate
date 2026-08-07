"""Tests for the v1→v2 upgrade pod entrypoint (``pyflyte-migrate upgrade-exec``) and ShimTaskResolver."""

import os
import sys
from types import SimpleNamespace

import flyte._deploy
import flyte._initialize
import flyte._internal.runtime.entrypoints as entrypoints
import flytekit
import pytest
from click.testing import CliRunner

from flyte_migrate._resolver import ShimTaskResolver
from flyte_migrate.cli import main

WF_SOURCE = """\
from flytekit import task, workflow


@task
def upexec_double(x: int) -> int:
    return x * 2


@workflow
def upexec_wf(x: int) -> int:
    return upexec_double(x=x)
"""


@pytest.fixture
def runner(monkeypatch, tmp_path):
    monkeypatch.setattr(os, "_exit", lambda code: None)
    monkeypatch.delenv("FLYTE_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("admin:\n  endpoint: dns:///fake.example.com\n  insecure: true\n")
    return CliRunner()


def test_shimmed_templates_carry_shim_resolver():
    @flytekit.task
    def resolver_probe_task(x: int) -> int:
        return x

    @flytekit.workflow
    def resolver_probe_wf(x: int) -> int:
        return resolver_probe_task(x=x)

    for template in (resolver_probe_task, resolver_probe_wf):
        assert isinstance(template.task_resolver, ShimTaskResolver)
        assert template.task_resolver.import_path == "flyte_migrate._resolver.ShimTaskResolver"


def test_resolver_load_task_round_trip(tmp_path, monkeypatch):
    (tmp_path / "upexec_fixture.py").write_text(WF_SOURCE)
    monkeypatch.syspath_prepend(str(tmp_path))

    resolver = ShimTaskResolver()
    template = resolver.load_task(["mod", "upexec_fixture", "instance", "upexec_wf"])
    assert isinstance(template.task_resolver, ShimTaskResolver)  # it's a shimmed v2 template
    assert resolver.loader_args(template, tmp_path) == ["mod", "upexec_fixture", "instance", "upexec_wf"]


def test_upgrade_exec_builds_images_and_execs_a0(runner, tmp_path, monkeypatch):
    (tmp_path / "upexec_mod.py").write_text(WF_SOURCE)

    execvp_calls = []
    monkeypatch.setattr(os, "execvp", lambda prog, argv: execvp_calls.append((prog, argv)))
    monkeypatch.setattr(flyte._initialize, "init_in_cluster", lambda *a, **kw: {})
    built = []
    monkeypatch.setattr(
        flyte._deploy,
        "build_images",
        lambda env: built.append(env) or SimpleNamespace(to_transport="img-cache-transport"),
    )

    a0_args = [
        "--inputs",
        "s3://bucket/inputs.pb",
        "--outputs-path",
        "s3://bucket/out",
        "--version",
        "v1abc",
        "--dest",
        str(tmp_path),
        "--resolver",
        "flyte_migrate._resolver.ShimTaskResolver",
        "mod",
        "upexec_mod",
        "instance",
        "upexec_wf",
    ]
    result = runner.invoke(main, ["upgrade-exec", *a0_args])
    assert result.exit_code == 0, result.output

    from flyte_migrate._workflow import parent_env

    assert built == [parent_env]
    ((prog, argv),) = execvp_calls
    assert prog == "a0"
    assert argv == ["a0", *a0_args, "--image-cache", "img-cache-transport"]
    sys.modules.pop("upexec_mod", None)


def test_upgrade_exec_downloads_tgz_before_import(runner, tmp_path, monkeypatch):
    dest = tmp_path / "bundle"
    dest.mkdir()

    downloads = []

    async def fake_download(bundle):
        # Simulate the tarball materializing the user module at --dest.
        downloads.append(bundle)
        (dest / "upexec_tgz_mod.py").write_text(WF_SOURCE)
        return bundle

    monkeypatch.setattr(entrypoints, "download_code_bundle", fake_download)
    monkeypatch.setattr(os, "execvp", lambda prog, argv: None)
    monkeypatch.setattr(flyte._initialize, "init_in_cluster", lambda *a, **kw: {})
    monkeypatch.setattr(flyte._deploy, "build_images", lambda env: SimpleNamespace(to_transport="t"))

    result = runner.invoke(
        main,
        [
            "upgrade-exec",
            "--inputs",
            "s3://b/i.pb",
            "--outputs-path",
            "s3://b/o",
            "--version",
            "v2def",
            "--tgz",
            "s3://b/fast-register.tar.gz",
            "--dest",
            str(dest),
            "--resolver",
            "flyte_migrate._resolver.ShimTaskResolver",
            "mod",
            "upexec_tgz_mod",
            "instance",
            "upexec_wf",
        ],
    )
    assert result.exit_code == 0, result.output
    (bundle,) = downloads
    assert bundle.tgz == "s3://b/fast-register.tar.gz"
    assert bundle.destination == str(dest)
    assert bundle.computed_version == "v2def"
    assert "upexec_tgz_mod" in sys.modules
    sys.modules.pop("upexec_tgz_mod", None)


def test_upgrade_exec_requires_module(runner):
    result = runner.invoke(main, ["upgrade-exec", "--inputs", "x", "--outputs-path", "y"])
    assert result.exit_code != 0
    assert "mod" in result.output
