# flyte-migrate

**Seamlessly migrate your FlyteKit v1 workflows to Flyte v2 without rewriting your code.**

## What is flyte-migrate?

`flyte-migrate` is a compatibility layer that allows your existing flyte v1 workflows to run on Flyte v2 infrastructure. Instead of rewriting thousands of lines of workflow code, simply import `flyte_migrate` alongside your existing code and continue using familiar v1 APIs.

Think of it as a translator: your v1 code speaks to `flyte-migrate`, and `flyte-migrate` speaks to Flyte v2.

## Why use flyte-migrate?

- **Zero Code Rewrites**: Keep using flytekit syntax you already know
- **Gradual Migration**: Migrate workflows incrementally at your own pace
- **Reduced Risk**: Test v2 infrastructure without changing your codebase
- **Full Feature Support**: Tasks, workflows, dynamic tasks, map tasks, and plugins all work
- **Plugin Compatibility**: Ray, Spark, Dask, PyTorch plugins are automatically translated

## Quick Start

### Installation

```bash
pip install flyte-migrate
```

### Basic Usage

Your existing FlyteKit v1 code:

```python
from flytekit import task, workflow

@task
def greet(name: str) -> str:
    return f"Hello, {name}!"

@workflow
def hello_workflow(name: str) -> str:
    return greet(name=name)
```

To run on Flyte v2, just add one import:

```python
import flyte_migrate  # Add this line
from flytekit import task, workflow

@task
def greet(name: str) -> str:
    return f"Hello, {name}!"

@workflow
def hello_workflow(name: str) -> str:
    return greet(name=name)
```

That's it! Your v1 workflow now runs on Flyte v2.

### Running Workflows

Execute locally:

```python
import flyte

flyte.init_from_config()
result = flyte.with_runcontext(mode="local").run(hello_workflow, name="World")
```

Execute remotely:

```python
run = flyte.with_runcontext(mode="remote").run(hello_workflow, name="World")
print(run.url)
```

## Examples

The `examples/` directory contains runnable examples demonstrating various v1 API patterns. Each example can be run directly:

```bash
python examples/hello.py
```

### Core Examples

| Example | File | v1 APIs Demonstrated |
|---------|------|---------------------|
| Hello World | [`examples/hello.py`](examples/hello.py) | `@task`, `@workflow`, `@dynamic`, `ImageSpec`, `cache`, `retries` |
| Map Task | [`examples/map_task.py`](examples/map_task.py) | `map_task`, `functools.partial` |
| File I/O | [`examples/file_io_example.py`](examples/file_io_example.py) | `FlyteFile`, `FlyteDirectory` |
| Complex Types | [`examples/complex_types_example.py`](examples/complex_types_example.py) | `@dataclass` types, `List` types, nested dataclasses |
| Conditionals | [`examples/conditional_example.py`](examples/conditional_example.py) | Task-level conditionals (workflow-level `conditional()` not yet supported) |
| Nested Workflows | [`examples/nested_workflow_example.py`](examples/nested_workflow_example.py) | Workflow composition (workflow calling workflow) |
| Error Handling | [`examples/error_handling_example.py`](examples/error_handling_example.py) | `retries`, `timeout`, error patterns |
| Secrets | [`examples/secret_example.py`](examples/secret_example.py) | `Secret`, `MountType.FILE`, `env_var` |
| Launch Plans | [`examples/launchplan_example.py`](examples/launchplan_example.py) | Workflow patterns (LaunchPlan.get_or_create not yet supported) |
| Deck / Reports | [`examples/deck_example.py`](examples/deck_example.py) | `enable_deck`, `Deck`, v2 report conversion |

### Plugin Examples

| Example | File | v1 APIs Demonstrated |
|---------|------|---------------------|
| Ray | [`examples/plugins/ray_example.py`](examples/plugins/ray_example.py) | `RayJobConfig`, `WorkerNodeConfig`, `HeadNodeConfig`, `Resources` |
| Spark | [`examples/plugins/spark_example.py`](examples/plugins/spark_example.py) | `Spark` plugin config, `spark_session` context |
| PyTorch | [`examples/plugins/pytorch_example.py`](examples/plugins/pytorch_example.py) | `Elastic` (PyTorch distributed training) |
| Dask | [`examples/plugins/dask_example.py`](examples/plugins/dask_example.py) | `Dask` plugin config |

## How It Works

`flyte-migrate` provides shimmed implementations of flytekit v1 APIs that:

1. Accept v1-style configurations
2. Translate them to Flyte v2 equivalents
3. Execute using the Flyte v2 engine

This means you get:
- The familiarity of v1 syntax
- The performance and features of v2 infrastructure
- A clear path to eventual full v2 adoption

## API Coverage

### Supported v1 APIs

| Category | API | Status | Example |
|----------|-----|--------|---------|
| **Decorators** | `@task` | Supported | `hello.py` |
| | `@workflow` | Supported | `hello.py` |
| | `@dynamic` | Supported | `hello.py` |
| **Task Config** | `cache` / `cache_version` | Supported | `hello.py` |
| | `retries` | Supported | `error_handling_example.py` |
| | `timeout` | Supported | `error_handling_example.py` |
| | `interruptible` | Supported | - |
| | `container_image` | Supported | `hello.py` |
| | `secret_requests` | Supported | `secret_example.py` |
| | `enable_deck` | Supported | `deck_example.py` |
| | `environment` | Supported | - |
| **Resources** | `Resources` (cpu, mem, gpu) | Supported | `ray_example.py` |
| | `requests` / `limits` | Supported | `ray_example.py` |
| | `accelerator` | Supported | - |
| | `shared_memory` | Supported | - |
| **Images** | `ImageSpec` | Supported | `hello.py` |
| | `base_image` | Supported | `spark_example.py` |
| | `apt_packages` / `packages` | Supported | `hello.py` |
| **Types** | `FlyteFile` | Supported | `file_io_example.py` |
| | `FlyteDirectory` | Supported | `file_io_example.py` |
| | `@dataclass` | Supported | `complex_types_example.py` |
| | `List`, `Tuple`, primitives | Supported | Various |
| **Patterns** | `map_task` | Supported | `map_task.py` |
| | `LaunchPlan` (as trigger) | Supported | `launchplan.py` |
| | Nested workflows | Supported | `nested_workflow_example.py` |
| **Plugins** | Ray (`RayJobConfig`) | Supported | `ray_example.py` |
| | Spark (`Spark`) | Supported | `spark_example.py` |
| | PyTorch (`Elastic`) | Supported | `pytorch_example.py` |
| | Dask (`Dask`) | Supported | `dask_example.py` |
| **Context** | `current_context()` | Supported | `spark_example.py` |
| | `spark_session` | Supported | `spark_example.py` |
| **Secrets** | `Secret` (env var) | Supported | `secret_example.py` |
| | `Secret` (file mount) | Supported | `secret_example.py` |

### Not Yet Supported

| API | Notes |
|-----|-------|
| `conditional()` | Workflow-level branching not yet shimmed - use task-level conditionals instead |
| `LaunchPlan.get_or_create` | LaunchPlan creation not shimmed - use workflows directly |
| `PodTemplate` | Stubbed (returns None) |
| `reference_task` / `reference_workflow` | Not yet implemented |
| `ContainerTask` | Not yet implemented |
| `approve` / `wait_for_input` | Not yet implemented |
| `StructuredDataset` | Not yet tested |

## Requirements

- Python 3.10 or higher
- Flyte v2 SDK (`flyte` package)
- `flytekit`

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/flyteorg/flyte-migrate.git
cd flyte-migrate

# Install in development mode
pip install -e .
```

## FAQ

**Q: Will this work with all my v1 workflows?**
A: Most v1 workflows should work. If you encounter issues, please open an issue on GitHub.

**Q: Is there a performance penalty?**
A: The translation overhead is minimal. Your tasks run directly on Flyte v2 infrastructure.

**Q: When should I fully migrate to v2?**
A: Use `flyte-migrate` to buy time and reduce risk. Migrate to native v2 APIs when convenient.

**Q: Can I mix v1 and v2 code?**
A: Yes! You can gradually introduce v2 code while keeping v1 code working via `flyte-migrate`.

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details.
