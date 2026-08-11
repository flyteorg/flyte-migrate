<h1 align="center">flyte-migrate</h1>

<p align="center">
  <strong>Migrate FlyteKit v1 workflows to Flyte v2 — without changing a single line of code.</strong>
</p>

<p align="center">
  <a href="https://github.com/flyteorg/flyte-migrate/actions"><img src="https://github.com/flyteorg/flyte-migrate/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://pypi.org/project/flyte-migrate/"><img src="https://img.shields.io/pypi/v/flyte-migrate" alt="PyPI"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python"></a>
  <a href="https://github.com/flyteorg/flyte-migrate/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-green" alt="License"></a>
</p>

---

## What is flyte-migrate?

`flyte-migrate` is a **zero-effort compatibility layer** that lets your existing FlyteKit v1 workflows run on Flyte v2 infrastructure. No rewrites, no refactoring — just add one import and deploy.

```diff
+ import flyte_migrate
  from flytekit import task, workflow

  @task(cache=True, retries=3)
  def greet(name: str) -> str:
      return f"Hello, {name}!"

  @workflow
  def hello_wf(name: str) -> str:
      return greet(name=name)
```

**That's it.** Your v1 workflow now runs on Flyte v2.

## Why flyte-migrate?

| Challenge | Without flyte-migrate | With flyte-migrate |
|-----------|----------------------|-------------------|
| Migrating 100+ workflows | Rewrite every file | Add one import per file |
| Testing on v2 infra | Full port required | Deploy existing code today |
| Risk of regressions | High — new code, new bugs | Zero — same logic, same behavior |
| Timeline | Weeks to months | Minutes |

## Quick Start

### Install

```bash
pip install flyte-migrate
```

### Add one line to your v1 code

```python
import flyte_migrate  # noqa: F401, I001  <-- add this as the first import
```

### Run on Flyte v2

```python
import flyte_migrate  # noqa: F401, I001
import logging
from flytekit import task, workflow, ImageSpec

image = ImageSpec(packages=["pandas"])

@task(container_image=image, cache=True, retries=3)
def process(data: str) -> str:
    return data.upper()

@workflow
def my_workflow(data: str) -> str:
    return process(data=data)

if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote").run(my_workflow, data="hello")
    print(run.url)
```

### Or use the CLI

Installing `flyte-migrate` also gives you `pyflyte-migrate`, which mirrors the `pyflyte` UX
against a v2 cluster. Files driven by the CLI don't need the `import flyte_migrate` line —
the shim is applied automatically before your file is loaded.

Try it on the examples in this repo:

```bash
# Run locally (pyflyte semantics: local by default)
pyflyte-migrate run examples/hello.py wf --name=flyte

# Run on the v2 cluster
pyflyte-migrate run --remote -p my-project -d development examples/hello.py wf --name=flyte

# Register (deploy) workflows from files or directories
pyflyte-migrate register -p my-project -d development examples/hello.py examples/launchplan.py
```

Cluster connection uses the standard v2 config discovery (`./config.yaml`, `.flyte/config.yaml`,
`~/.flyte/config.yaml`, ...), overridable with `-c /path/to/config.yaml` or a `FLYTE_API_KEY`
environment variable. Each registered file gets its own per-module environment, so files that
define same-named workflows don't collide.

## What Gets Translated

`flyte-migrate` intercepts v1 API calls at import time and translates them to v2 equivalents. Here's what's covered:

### Core APIs

| v1 API | v2 Equivalent | Status |
|--------|--------------|--------|
| `@task` | `TaskEnvironment.task()` | Fully supported |
| `@workflow` | `TaskEnvironment.task()` | Fully supported |
| `@dynamic` | `TaskEnvironment.task()` | Fully supported |
| `map_task()` | `flyte.map()` | Supported (incl. concurrency) |
| `LaunchPlan` | `Trigger` (Cron / FixedRate) | Fully supported |
| `Deck` | `flyte.report` | Fully supported |
| `@reference_task` | `TaskDetails.get()` | Fully supported |

### Task Parameters

All commonly used `@task` parameters are translated:

| Parameter | Translation |
|-----------|------------|
| `cache` / `cache_version` | `cache="auto"` / `"disable"` |
| `retries`, `timeout`, `interruptible` | Passed through directly |
| `container_image` (str or `ImageSpec`) | Converted to `flyte.Image` |
| `requests` / `limits` / `resources` | Merged into `flyte.Resources` |
| `secret_requests` | Converted to `flyte.Secret` (ENV_VAR and FILE mounts) |
| `environment` | Mapped to `env_vars` |
| `pod_template` / `pod_template_name` | Passed through to v2 `PodTemplate` |
| `enable_deck` | Mapped to `report=True` |
| `docs` | `short_description` mapped to `description` |
| `task_config` | Dispatched to plugin transformers |
| `accelerator` + `gpu` | Formatted as `"device:count"` |
| `shared_memory` | `True` → `"auto"`, string passthrough |

### ImageSpec

All `ImageSpec` fields are translated, including:
- `packages` (with automatic v1 → v2 plugin name mapping)
- `apt_packages`, `pip_index`, `pip_extra_index_url`, `pip_extra_args`
- `base_image` (string or nested `ImageSpec`)
- `python_version`, `registry`, `platform`
- `env`, `commands`, `requirements`, `copy`, `source_root`
- `pip_secret_mounts` → `flyte.Secret` objects

Plugin package names are automatically translated:

```
flytekitplugins-spark    → flyteplugins-spark
flytekitplugins-ray      → flyteplugins-ray
flytekitplugins-dask     → flyteplugins-dask
flytekitplugins-kfpytorch → flyteplugins-pytorch
```

### Plugins

| Plugin | Config Class | Support |
|--------|-------------|---------|
| **Spark** | `Spark` | spark_conf, hadoop_conf, driver/executor pod templates |
| **Ray** | `RayJobConfig` | Head/worker nodes, autoscaling, runtime_env |
| **PyTorch** | `Elastic` | Multi-node, RunPolicy, NCCL configs |
| **Dask** | `Dask` | Worker groups, scheduler config |
| **BigQuery** | `BigQueryConfig` | Query tasks |

### Data Types

All v1 type patterns work transparently through the shim:

- Primitives: `int`, `float`, `str`, `bool`, `datetime`
- Collections: `List[T]`, `Dict[K, V]`, `Tuple[T, ...]`, `Optional[T]`
- Structured: `NamedTuple`, `@dataclass`, `Enum`
- Flyte types: `FlyteFile`, `FlyteDirectory`, `StructuredDataset`
- Annotated types: `typing.Annotated[T, ...]`

## Architecture

```
┌─────────────────────────────────────┐
│         Your v1 Code                │
│  @task, @workflow, ImageSpec, ...   │
└──────────────┬──────────────────────┘
               │  import flyte_migrate
               ▼
┌─────────────────────────────────────┐
│         flyte-migrate shim          │
│                                     │
│  _task.py      → @task decorator    │
│  _workflow.py  → @workflow decorator│
│  _dynamic.py   → @dynamic decorator│
│  _map.py       → map_task()        │
│  _launchplan.py→ LaunchPlan        │
│  _reference.py → @reference_task   │
│  _image.py     → ImageSpec→Image   │
│  _resource.py  → Resources merge   │
│  _secret.py    → Secret transform  │
│  _pod_template.py → PodTemplate    │
│  _deck.py      → Deck→Report      │
│  _context.py   → ExecutionParams   │
│  _plugins/     → Spark,Ray,Dask,...│
└──────────────┬──────────────────────┘
               │  translated v2 calls
               ▼
┌─────────────────────────────────────┐
│         Flyte v2 SDK                │
│  TaskEnvironment, Image, Resources  │
└─────────────────────────────────────┘
```

## Known Limitations

Some v1 features have no v2 equivalent and are handled gracefully:

| Feature | Behavior |
|---------|----------|
| `conda_packages` / `conda_channels` | Warning logged, ignored |
| `builder="envd"` / `"noop"` | Warning logged, ignored |
| `cache_version` | Accepted (no-op in v2) |
| `execution_mode`, `task_resolver`, `pickle_untyped` | Logged, ignored |
| `map_task` `min_successes` / `min_success_ratio` | Accepted but not forwarded (v2 doesn't support) |
| `gpu` count without named accelerator | v2 requires device name (e.g. `"T4:1"`) |
| `docs.long_description` | Only `short_description` is mapped |
| `flytekit.conditional()` | Use native Python `if/else` in workflows |

## Examples

The [`examples/`](examples/) directory contains runnable examples for every feature:

| Example | What it tests |
|---------|--------------|
| [`hello.py`](examples/hello.py) | Basic task, workflow, dynamic, cache, retries |
| [`conditional_wf.py`](examples/conditional_wf.py) | Branching with native Python if/else |
| [`map_task.py`](examples/map_task.py) | Mapped tasks with `functools.partial` |
| [`launchplan.py`](examples/launchplan.py) | Cron and FixedRate schedules |
| [`secret_example.py`](examples/secret_example.py) | ENV_VAR and FILE secret mounts |
| [`deck_example.py`](examples/deck_example.py) | HTML reports via Deck |
| [`image.py`](examples/image.py) | ImageSpec with packages, apt, env, commands |
| [`v2_image.py`](examples/v2_image.py) | Mixing v1 and v2: a v1 task using a v2 `flyte.Image` |
| [`pod_template_example.py`](examples/pod_template_example.py) | Pod customization with labels, annotations |
| [`reference_task_example.py`](examples/reference_task_example.py) | Calling pre-registered remote tasks |
| [`datatypes_comprehensive.py`](examples/datatypes_comprehensive.py) | NamedTuple, dataclass, Enum, FlyteFile |
| [`plugins/spark_example.py`](examples/plugins/spark_example.py) | Apache Spark jobs |
| [`plugins/ray_example.py`](examples/plugins/ray_example.py) | Ray distributed computing |
| [`plugins/pytorch_example.py`](examples/plugins/pytorch_example.py) | PyTorch distributed training |
| [`plugins/dask_example.py`](examples/plugins/dask_example.py) | Dask parallel computing |

## Development

```bash
# Clone and install
git clone https://github.com/flyteorg/flyte-migrate.git
cd flyte-migrate
uv sync

# Format, lint, test
make fmt
make lint
uv run pytest

# Run a single test
uv run pytest tests/test_transform_utils.py -v
```

## FAQ

**Do I need to change my v1 code?**
No. Add `import flyte_migrate` as the first import — everything else stays the same.

**What if I use plugins like Spark or Ray?**
They work. Plugin configs (spark_conf, worker nodes, etc.) are automatically translated to v2 equivalents. Plugin pip packages are also renamed automatically.

**Is there a performance overhead?**
The translation happens once at import time. At runtime, your tasks execute directly on v2 infrastructure with no overhead.

**Can I mix v1 and v2 code?**
Yes. You can gradually introduce native v2 code while keeping v1 code working through flyte-migrate — see [`examples/v2_image.py`](examples/v2_image.py) for a v1 task whose image is built with the v2 `flyte.Image` API.

**What Python versions are supported?**
Python 3.10+.

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
