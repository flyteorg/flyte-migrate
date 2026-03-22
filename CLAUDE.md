# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is flyte-migrate?

A compatibility layer (shim) that lets FlyteKit v1 workflows run on Flyte v2 infrastructure without code rewrites. Users add `import flyte_migrate` to their existing v1 code, and the module patches flytekit's namespace (`@task`, `@workflow`, `@dynamic`, `map_task`, `LaunchPlan`, `Deck`) to translate v1 API calls into v2 equivalents at runtime.

## Build & Development Commands

This project uses `uv` as the package manager.

```bash
# Install dependencies
uv sync

# Format code
make fmt

# Check formatting (CI uses this)
make fmt-check

# Lint
make lint

# Type check
make mypy

# Run all tests
uv run pytest

# Run a single test
uv run pytest tests/test_foo.py::test_name -v

# Build wheel
make dist
```

## Architecture

The shim works by patching flytekit's module namespace on import. The entry point is `src/flyte_migrate/__init__.py` which replaces v1 decorators/classes with shimmed versions:

- **`_task.py`** — `task_shim`: intercepts `@task` decorator, translates v1 config (cache, retries, resources, secrets, plugins, pod templates) → v2 `TaskEnvironment`
- **`_workflow.py`** — creates a parent `TaskEnvironment` and routes `@workflow` through it
- **`_context.py`** — patches `ExecutionParameters.__getattr__` to bridge v1 context access to v2 runtime
- **`_dynamic.py`** — routes `@dynamic` through `task_shim`
- **`_map.py`** — `MapShim` wraps `flyte.map()` with v1-style interface
- **`_launchplan.py`** — transforms v1 `LaunchPlan` → v2 `Trigger` (Cron, FixedRate schedules)
- **`_deck_to_report.py`** — replaces `flytekit.Deck` with v2-compatible `_DeckV2` that routes to v2 reports

### Transformation utilities

- **`_image.py`** — converts v1 `ImageSpec` → v2 `Image` (handles pip/apt packages, env vars, base images, plugin package name mapping like `flytekitplugins-spark` → `flyteplugins-spark`)
- **`_resource.py`** — converts v1 `Resources` (requests/limits) → v2 `Resources` with GPU/accelerator support
- **`_secret.py`** — converts v1 `Secret` → v2 `Secret` (FILE vs ENV_VAR mount types)
- **`_pod_template.py`** — wraps v1 `PodTemplate` → v2 `PodTemplate`

### Plugin system (`_plugins/`)

`_plugins/__init__.py` dispatches v1 plugin configs to the appropriate transformer. Supported plugins: Spark, Ray, Dask, PyTorch. Each plugin module translates its v1 config to v2 equivalents (e.g., `spark.py` maps driver/executor pod templates, `ray.py` converts head/worker node configs with autoscaling).

## Code Style

- Line length: 120 characters
- Linter/formatter: ruff (see `[tool.ruff]` in pyproject.toml for rule selection)
- Type checker: mypy with `ignore_missing_imports = true`
- Examples in `examples/` are exempt from E402 (module-level import ordering)
