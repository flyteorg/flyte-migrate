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

`flyte-migrate` is a **zero-effort compatibility layer** that lets your existing FlyteKit v1 workflows run on Flyte v2 infrastructure. No rewrites, no refactoring — **not a single line of code changes**.

Take your existing v1 file, untouched:

```python
from flytekit import task, workflow

@task(cache=True, retries=3)
def greet(name: str) -> str:
    return f"Hello, {name}!"

@workflow
def hello_wf(name: str) -> str:
    return greet(name=name)
```

And run it on Flyte v2 with `pyflyte-migrate` — a drop-in replacement for `pyflyte`:

```bash
pip install flyte-migrate

pyflyte-migrate run --remote hello.py hello_wf --name=flyte
```

**That's it.** The shim is applied automatically before your file is loaded, so your v1 code
runs on v2 unmodified.

> [!NOTE]
> `flyte-migrate` is a quick way to try Flyte v2 without changing any code, but it may hit
> edge cases that are not covered yet or cannot be migrated automatically (see
> [Known Limitations](#known-limitations)). For a long-term migration we still recommend
> rewriting your workflows with the v2 SDK, following the
> [migration guide](https://www.union.ai/docs/v2/flyte/user-guide/migration/flyte-2/).

## Why flyte-migrate?

| Challenge | Without flyte-migrate | With flyte-migrate |
|-----------|----------------------|-------------------|
| Migrating 100+ workflows | Rewrite every file | Run them as-is with `pyflyte-migrate` |
| Testing on v2 infra | Full port required | Deploy existing code today |
| Risk of regressions | High — new code, new bugs | Zero — same logic, same behavior |
| Timeline | Weeks to months | Minutes |
| Adopting v2 features | All-or-nothing rewrite | Per-task — mix v1 and v2 in one file |

## Quick Start

### Install

```bash
pip install flyte-migrate
```

### Run your v1 code with the CLI (no code changes)

Installing `flyte-migrate` also gives you `pyflyte-migrate`, which mirrors the `pyflyte` UX
against a v2 cluster. The shim is applied automatically before your file is loaded, so your
files need **no** `import flyte_migrate` line.

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

### Or drive it yourself with the v2 remote API

If you'd rather call the Flyte v2 API from your own script and launch it with `python my_file.py`,
add `import flyte_migrate` as the **first** import — nothing applies the shim for you in that case:

```python
import flyte_migrate  # noqa: F401, I001  <-- must be the first import
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

```bash
python my_file.py
```

## Hybrid Mode: Mix v1 and v2 in the Same File

You don't have to migrate all at once. v1 and v2 APIs coexist, so you can swap individual
pieces over to the v2 SDK while the rest of the file stays v1.

For example, use a v2 `flyte.Image` instead of a v1 `ImageSpec` to build the image for a v1
task — no `ImageSpec` translation involved, the image is used exactly as you defined it:

```python
import flyte
from flytekit import task, workflow

# v2 image API, used by a v1 task
image = flyte.Image.from_debian_base().with_pip_packages("flytekit", "flyte-migrate", "pandas")

@task(container_image=image, cache=True, retries=2)   # still v1
def summarize(name: str) -> str:
    import pandas as pd

    df = pd.DataFrame({"name": [name]})
    return f"Hello, {df.at[0, 'name']}!"

@workflow                                             # still v1
def wf(name: str) -> str:
    return summarize(name=name)
```

`container_image` accepts any of these, so migration is a per-task decision:

| You pass | What happens |
|----------|--------------|
| `flyte.Image` (v2) | Used **as-is**, untouched — you control the whole image |
| `ImageSpec` (v1) | Translated to a `flyte.Image`, with `flyte-migrate` added |
| `str` (image ref) | Wrapped as an extendable base, with `flyte` + `flyte-migrate` added |
| omitted | Default debian base with `flytekit` + `flyte-migrate` |

> [!IMPORTANT]
> A `flyte.Image` is used verbatim, so it must install `flytekit` **and** `flyte-migrate`
> — otherwise the container can't load your v1 file.

See [`examples/v2_image.py`](examples/v2_image.py) for the full runnable version.

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
| `@reference_task` / `@reference_workflow` / `@reference_launch_plan` | `TaskDetails.get()` | Fully supported |
| `wait_for_input()` / `approve()` | `flyte.new_condition(...).wait()` | Supported (see gate node note) |
| `sleep()` | `time.sleep` in the workflow driver | Fully supported |

### Task Parameters

All commonly used `@task` parameters are translated:

| Parameter | Translation |
|-----------|------------|
| `cache` | `cache="auto"` / `"disable"` |
| `cache_version` (or `Cache(version=...)`) | `Cache(behavior="override", version_override=...)` |
| `cache_serialize`, `cache_ignore_input_vars` | `Cache(serialize=...)` / `Cache(ignored_inputs=...)` |
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
┌──────────────────────────────────────────┐
│               Your v1 Code               │
│     @task, @workflow, ImageSpec, ...     │
└────────────────────┬─────────────────────┘
                     │  pyflyte-migrate (or import flyte_migrate)
                     ▼
┌──────────────────────────────────────────┐
│            flyte-migrate shim            │
│                                          │
│  _task.py         → @task decorator      │
│  _workflow.py     → @workflow decorator  │
│  _dynamic.py      → @dynamic decorator   │
│  _map.py          → map_task()           │
│  _launchplan.py   → LaunchPlan           │
│  _reference.py    → @reference_task      │
│  _image.py        → ImageSpec → Image    │
│  _resource.py     → Resources merge      │
│  _secret.py       → Secret transform     │
│  _pod_template.py → PodTemplate          │
│  _deck.py         → Deck → Report        │
│  _context.py      → ExecutionParams      │
│  _plugins/        → Spark, Ray, Dask, ...│
└────────────────────┬─────────────────────┘
                     │  translated v2 calls
                     ▼
┌──────────────────────────────────────────┐
│               Flyte v2 SDK               │
│    TaskEnvironment, Image, Resources     │
└──────────────────────────────────────────┘
```

## Known Limitations

Some v1 features have no v2 equivalent and are handled gracefully:

| Feature | Behavior |
|---------|----------|
| `conda_packages` / `conda_channels` | Warning logged, ignored |
| `builder="envd"` / `"noop"` | Warning logged, ignored |
| `wait_for_input` non-scalar `expected_type` | `TypeError` — v2 conditions carry `bool` / `int` / `float` / `str` only |
| `execution_mode`, `task_resolver`, `pickle_untyped` | Logged, ignored |
| `map_task` `min_successes` / `min_success_ratio` | Enforced client-side — v2 has no native equivalent |
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
No. Run it with `pyflyte-migrate` and your files stay exactly as they are. The only case that
needs an edit is driving the Flyte v2 remote API yourself (`python my_file.py`), where you add
`import flyte_migrate` as the first import.

**What if I use plugins like Spark or Ray?**
They work. Plugin configs (spark_conf, worker nodes, etc.) are automatically translated to v2 equivalents. Plugin pip packages are also renamed automatically.

**Is there a performance overhead?**
The translation happens once at import time. At runtime, your tasks execute directly on v2 infrastructure with no overhead.

**Can I mix v1 and v2 code?**
Yes — see [Hybrid Mode](#hybrid-mode-mix-v1-and-v2-in-the-same-file). You can gradually introduce native v2 code while keeping v1 code working through flyte-migrate, e.g. a v1 `@task` whose image is built with the v2 `flyte.Image` API.

**What Python versions are supported?**
Python 3.10+.

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
