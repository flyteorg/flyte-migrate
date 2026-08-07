"""Tests for stamping _F_SYS_PATH onto environments at deploy time."""

import sys

import flyte
from flyte._constants import FLYTE_SYS_PATH

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate import _deploy


class _FakeTask:
    def __init__(self, env_vars=None):
        self.env_vars = env_vars


class _FakeEnv:
    """Stand-in for a TaskEnvironment — env_vars, _tasks and depends_on are what matter."""

    def __init__(self, name, env_vars=None, depends_on=(), tasks=None):
        self.name = name
        self.env_vars = env_vars
        self.depends_on = list(depends_on)
        self._tasks = tasks or {}


def _patch_config(monkeypatch, root_dir, sync=True):
    class _Cfg:
        sync_local_sys_paths = sync

    _Cfg.root_dir = root_dir
    monkeypatch.setattr(_deploy, "get_init_config", lambda: _Cfg)


class TestDeployIsPatched:
    def test_flyte_deploy_is_the_shim(self):
        assert flyte.deploy is _deploy.deploy_shim

    def test_shim_keeps_the_async_entrypoint(self):
        """flyte.deploy is syncified; callers may use .aio."""
        assert hasattr(flyte.deploy, "aio")


class TestStampSysPath:
    def test_stamps_paths_under_the_root_dir(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(str(tmp_path / "src"))
        _patch_config(monkeypatch, tmp_path)

        env = _FakeEnv("parent")
        _deploy._stamp_sys_path([env])
        assert env.env_vars[FLYTE_SYS_PATH] == "./src"

    def test_walks_depends_on(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(str(tmp_path / "src"))
        _patch_config(monkeypatch, tmp_path)

        child, grandchild = _FakeEnv("child"), _FakeEnv("grandchild")
        child.depends_on = [grandchild]
        parent = _FakeEnv("parent", depends_on=[child])

        _deploy._stamp_sys_path([parent])
        for env in (parent, child, grandchild):
            assert env.env_vars[FLYTE_SYS_PATH] == "./src"

    def test_survives_a_dependency_cycle(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(str(tmp_path / "src"))
        _patch_config(monkeypatch, tmp_path)

        a, b = _FakeEnv("a"), _FakeEnv("b")
        a.depends_on, b.depends_on = [b], [a]
        _deploy._stamp_sys_path([a])
        assert a.env_vars[FLYTE_SYS_PATH] == "./src"

    def test_stamps_task_templates(self, tmp_path, monkeypatch):
        """The container env is serialized from the task template, not the environment."""
        monkeypatch.syspath_prepend(str(tmp_path / "src"))
        _patch_config(monkeypatch, tmp_path)

        task = _FakeTask()
        env = _FakeEnv("parent", tasks={"parent.wf": task})
        _deploy._stamp_sys_path([env])
        assert task.env_vars[FLYTE_SYS_PATH] == "./src"

    def test_existing_value_is_not_clobbered(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(str(tmp_path / "src"))
        _patch_config(monkeypatch, tmp_path)

        env = _FakeEnv("parent", env_vars={FLYTE_SYS_PATH: "./mine"})
        _deploy._stamp_sys_path([env])
        assert env.env_vars[FLYTE_SYS_PATH] == "./mine"

    def test_other_env_vars_are_preserved(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(str(tmp_path / "src"))
        _patch_config(monkeypatch, tmp_path)

        env = _FakeEnv("parent", env_vars={"KEEP": "1"})
        _deploy._stamp_sys_path([env])
        assert env.env_vars["KEEP"] == "1"
        assert FLYTE_SYS_PATH in env.env_vars

    def test_noop_when_sync_disabled(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(str(tmp_path / "src"))
        _patch_config(monkeypatch, tmp_path, sync=False)

        env = _FakeEnv("parent")
        _deploy._stamp_sys_path([env])
        assert env.env_vars is None

    def test_noop_when_uninitialized(self, monkeypatch):
        monkeypatch.setattr(_deploy, "get_init_config", lambda: None)
        env = _FakeEnv("parent")
        _deploy._stamp_sys_path([env])
        assert env.env_vars is None

    def test_noop_when_no_path_is_under_the_root(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "path", ["/somewhere/else"])
        _patch_config(monkeypatch, tmp_path)

        env = _FakeEnv("parent")
        _deploy._stamp_sys_path([env])
        assert env.env_vars is None


class TestDeployShim:
    def test_stamps_then_delegates(self, tmp_path, monkeypatch):
        monkeypatch.syspath_prepend(str(tmp_path / "src"))
        _patch_config(monkeypatch, tmp_path)

        seen = {}

        def _fake_deploy(*envs, **kwargs):
            seen["env_vars"] = envs[0].env_vars
            seen["kwargs"] = kwargs
            return ["deployment"]

        monkeypatch.setattr(_deploy, "_original_deploy", _fake_deploy)

        env = _FakeEnv("parent")
        assert _deploy.deploy_shim(env, dryrun=True) == ["deployment"]
        # stamped before the underlying deploy saw it, not after
        assert seen["env_vars"][FLYTE_SYS_PATH] == "./src"
        assert seen["kwargs"] == {"dryrun": True}


class TestInheritedSysPath:
    """Child task envs inherit _F_SYS_PATH from the parent container at import time."""

    def test_returns_the_value_from_the_environment(self, monkeypatch):
        monkeypatch.setenv(FLYTE_SYS_PATH, "./src:./.")
        assert _deploy.inherited_sys_path() == {FLYTE_SYS_PATH: "./src:./."}

    def test_empty_when_unset(self, monkeypatch):
        monkeypatch.delenv(FLYTE_SYS_PATH, raising=False)
        assert _deploy.inherited_sys_path() == {}

    @staticmethod
    def _build_env(environment=None):
        from flyte_migrate._task import _build_task_environment

        def some_task():
            pass

        return _build_task_environment(
            some_task,
            cache=False,
            task_config=None,
            container_image=None,
            environment=environment,
            requests=None,
            limits=None,
            resources=None,
            accelerator=None,
            shared_memory=None,
            secret_requests=None,
            docs=None,
            pod_template=None,
            pod_template_name=None,
        )

    def test_task_env_picks_it_up(self, monkeypatch):
        """A parent container re-imports the module, so the env must be set at build time."""
        monkeypatch.setenv(FLYTE_SYS_PATH, "./src:./.")
        assert self._build_env().env_vars[FLYTE_SYS_PATH] == "./src:./."

    def test_user_env_vars_win(self, monkeypatch):
        monkeypatch.setenv(FLYTE_SYS_PATH, "./src")
        env = self._build_env({"MINE": "1", FLYTE_SYS_PATH: "./theirs"})
        assert env.env_vars == {"MINE": "1", FLYTE_SYS_PATH: "./theirs"}

    def test_none_when_nothing_to_set(self, monkeypatch):
        monkeypatch.delenv(FLYTE_SYS_PATH, raising=False)
        assert self._build_env().env_vars is None
