# Contributing to flyte-migrate

`flyte-migrate` is a shim: users add `import flyte_migrate` to existing FlyteKit **v1** code, and we
patch flytekit's namespace so their `@task`/`@workflow`/`ImageSpec`/... calls are translated into
Flyte **v2** equivalents at runtime. Almost every contribution is one of:

- a v1 API that isn't translated yet, or is translated wrongly
- a v1 `@task` parameter that gets dropped on the way to v2
- a plugin config (Spark, Ray, Dask, PyTorch, BigQuery) that needs mapping
- an example that doesn't run on a real v2 cluster

See [`README.md`](README.md) for what's already covered and [`CLAUDE.md`](CLAUDE.md) for a
module-by-module map of the shim.

## Setup

The project uses [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync                 # install deps (including dev group)
uv run pytest           # unit tests — fast, no cluster needed
make fmt                # format + autofix (ruff)
make lint               # ruff check
make mypy               # mypy over src/
```

`make fmt-check`, `make lint`, and `make mypy` are exactly what CI runs
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)), so a clean local run means a green CI.

## Where your change goes

The shim's entry point is [`src/flyte_migrate/__init__.py`](src/flyte_migrate/__init__.py), which
swaps v1 names for shimmed versions at import time. From there:

| If you're changing... | Touch | Test in |
| --- | --- | --- |
| `@task` behavior or a `@task` parameter | `_task.py` | `tests/test_task_params.py` |
| `@workflow` / `@dynamic` | `_workflow.py`, `_dynamic.py` | `tests/test_subworkflow_dynamic.py` |
| `map_task` | `_map.py` | `tests/test_map.py` |
| `LaunchPlan` → `Trigger` (schedules) | `_launchplan.py` | `tests/test_control_flow_comprehensive.py` |
| `@reference_task` / `@reference_launch_plan` | `_reference.py` | `tests/test_reference_task.py` |
| `Deck` → v2 reports | `_deck.py` | `tests/test_deck_flush.py` |
| `ImageSpec` → `flyte.Image` | `_image.py` | `tests/test_image_comprehensive.py` |
| `Resources`, `Secret`, `PodTemplate` | `_resource.py`, `_secret.py`, `_pod_template.py` | `tests/test_resource_comprehensive.py`, `tests/test_secret_pod_comprehensive.py`, `tests/test_transform_utils.py` |
| v1 context (`flytekit.current_context()`) | `_context.py` | no unit coverage yet — an example plus its integration test is the current check |
| a plugin config | `_plugins/<name>.py` | `tests/test_spark_dask_plugins.py`, `tests/test_ray_pytorch_plugins.py` |
| the `pyflyte-migrate` CLI | `cli.py`, `_deploy.py` | `tests/test_cli.py`, `tests/test_deploy.py` |

Add an example under [`examples/`](examples/) whenever the change is user-visible — it doubles as
the integration test (see below).

### Adding a plugin

1. Write `_transform_<name>_config_v1_to_v2()` in `src/flyte_migrate/_plugins/<name>.py`, converting
   the v1 config object into its v2 equivalent. Return `None` if the input isn't the expected type.
2. Register it in [`_plugins/__init__.py`](src/flyte_migrate/_plugins/__init__.py) with
   `register_plugin("<V1ConfigClassName>", _transform_<name>_config_v1_to_v2)` — dispatch is by the
   v1 class's `__name__`, so no other file changes.
3. Add the package rename to `_PACKAGE_V1_TO_V2` in
   [`_image.py`](src/flyte_migrate/_image.py) (e.g. `flytekitplugins-foo` → `flyteplugins-foo`) so
   `ImageSpec(packages=[...])` installs the v2 package.
4. Add an example under `examples/plugins/` and an integration test marked `@pytest.mark.plugins`.

## Tests

**Unit tests** (`tests/`) run on every push and need no cluster. They assert the *translation* —
given a v1 config, the shim produces the right v2 objects. This is where most coverage belongs,
because it's fast and deterministic.

```bash
uv run pytest
uv run pytest tests/test_image_comprehensive.py::test_name -v
```

**Integration tests** ([`tests/integration/test_examples.py`](tests/integration/test_examples.py))
run one example per test against a real v2 cluster. They're deselected by default
(`addopts = -m 'not integration'`) and skipped without `FLYTE_API_KEY`, so they never slow down the
normal run:

```bash
FLYTE_API_KEY=... uv run pytest tests/integration -v -s -m integration
FLYTE_API_KEY=... uv run pytest tests/integration -v -s -m "integration and not plugins"
FLYTE_API_KEY=... uv run pytest tests/integration -v -s -m integration -k hello
```

The `plugins` marker covers examples needing cluster operators (Spark/Ray/Dask/PyTorch) or external
services (BigQuery). Adding a test for a new example is three lines:

```python
def test_hello():
    from examples.hello import wf

    _run_and_wait(wf, name="flyte")
```

The module docstring in that file explains the constraints — read it before adding one.

### When the bug is upstream

Some failures are genuine gaps in Flyte v2 that the shim can't bridge — the v1 code is valid and the
translation is correct, but v2 behaves differently. Don't work around those in the example. Mark the
test:

```python
@pytest.mark.xfail(strict=True, reason="<diagnosis, with file:line upstream>")
```

`strict=True` matters: the test still runs, and the moment upstream fixes it the suite goes red with
an `XPASS`, forcing the mark's removal. A `skip` would quietly outlive the bug. Put the full
diagnosis in `reason` so the next person doesn't re-derive it, and open an issue on
[`flyteorg/flyte`](https://github.com/flyteorg/flyte/issues).

## Pull requests

- Sign your commits: `git commit -s`.
- Keep the PR body in the shape the repo already uses: **Why are the changes needed?**, **What
  changes were proposed?** (per-file), **How was this patch tested?** (paste the command and its
  output). If you ran against a cluster, say which one and link the run.
- Line length is 120; ruff and mypy config live in `pyproject.toml`. Examples are exempt from E402
  (the `import flyte_migrate` line must come first).
- New behavior needs a unit test. Cluster-only behavior needs an example plus its integration test.

## Gotchas worth knowing

These cost real debugging time before they were understood:

- **Environment names come from `__module__`.** Each file gets its own `TaskEnvironment`, which is
  why six examples can all define `wf` without colliding. Loading a module under a synthetic name
  (what `importlib.util.spec_from_file_location` does) makes every module look identical and
  desyncs deploy-time names from what `@reference_task` resolves.
- **v2 plugin packages are pinned to the running `flyte` version** (`_pin_to_flyte_version` in
  `_image.py`). `flyteplugins-*` import `flyte` internals and release in lockstep; an unpinned
  plugin resolves to the newest release inside the image while `flyte` stays older, which surfaces
  as `ImportError: cannot import name 'system_logger' from 'flyte'`.
- **A v1 `PodTemplate` needs the `kubernetes` client at import time**
  (`flytekit.PodTemplate.__post_init__` does `from kubernetes.client import V1PodSpec`). Containers
  re-import the whole module, so *any* `PodTemplate` in a file means *every* task in that file needs
  the client — `with_kubernetes_client` in `_image.py` handles it per-module.
- **Pod templates can hide inside a plugin config** (`Spark(driver_pod=...)`), not just
  `@task(pod_template=...)`. Check both when reasoning about images and templates.
