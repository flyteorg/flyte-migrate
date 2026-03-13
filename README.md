# Flyte Migrate

**Seamlessly migrate your Flyte v1 workflows to v2 with zero code changes.**

## What is this?

`flyte-migrate` is a compatibility layer that lets you run your existing Flyte v1 code on Flyte v2 without rewriting anything. Simply add one import line, and you're ready to go.

## Why do you need this?

Flyte v2 brings powerful improvements, but migrating existing workflows can be time-consuming. This tool bridges the gap by:

- **Zero refactoring required** - Your v1 code works immediately on v2
- **Gradual migration** - Migrate at your own pace, one workflow at a time
- **Full compatibility** - Works with tasks, workflows, dynamic tasks, map tasks, and plugins
- **Production ready** - Battle-tested with real-world workflows

## Quick Start

### Installation

```bash
pip install flyte-migrate
```

### Usage

Add this single line at the top of your existing Flyte v1 code:

```python
import flyte_migrate  # noqa: F401, I001
```

That's it! Your v1 workflow now runs on v2.

### Before and After

**Your existing v1 code:**
```python
from flytekit import task, workflow, ImageSpec

image = ImageSpec(packages=["pandas", "numpy"])

@task(container_image=image, retries=3)
def process_data(name: str):
    print(f"Processing {name}")

@workflow
def my_workflow(name: str):
    process_data(name=name)
```

**Add one line to make it v2 compatible:**
```python
import flyte_migrate  # noqa: F401, I001

from flytekit import task, workflow, ImageSpec

image = ImageSpec(packages=["pandas", "numpy"])

@task(container_image=image, retries=3)
def process_data(name: str):
    print(f"Processing {name}")

@workflow
def my_workflow(name: str):
    process_data(name=name)
```

Done! No other changes needed.

## What gets migrated?

`flyte-migrate` automatically converts v1 patterns to v2:

- **Tasks** - All task configurations (resources, retries, caching, etc.)
- **Workflows** - Workflow definitions and dependencies
- **Dynamic tasks** - Runtime task generation
- **Map tasks** - Parallel execution patterns
- **Container images** - ImageSpec and custom images
- **Resources** - CPU, memory, GPU, and storage requests/limits
- **Plugins** - Ray, Spark, and other integrations
- **Secrets** - Environment variables and secret mounting
- **Pod templates** - Kubernetes pod customizations

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
| Conditionals | [`examples/conditional_example.py`](examples/conditional_example.py) | `conditional`, `.if_()`, `.else_()`, `.is_true()` |
| Nested Workflows | [`examples/nested_workflow_example.py`](examples/nested_workflow_example.py) | Workflow composition (workflow calling workflow) |
| Error Handling | [`examples/error_handling_example.py`](examples/error_handling_example.py) | `retries`, `timeout`, error patterns |
| Secrets | [`examples/secret_example.py`](examples/secret_example.py) | `Secret`, `MountType.FILE`, `env_var` |
| Launch Plans | [`examples/launchplan_example.py`](examples/launchplan_example.py) | `LaunchPlan`, `fixed_inputs`, `default_inputs` |

### Plugin Examples

| Example | File | v1 APIs Demonstrated |
|---------|------|---------------------|
| Ray | [`examples/plugins/ray_example.py`](examples/plugins/ray_example.py) | `RayJobConfig`, `WorkerNodeConfig`, `Resources` |
| Spark | [`examples/plugins/spark_example.py`](examples/plugins/spark_example.py) | `Spark` plugin config, `spark_session` context |

### Basic Task

```python
import flyte_migrate  # noqa: F401, I001

from flytekit import task, workflow

@task(cache=True, retries=3)
def say_hello(name: str):
    print(f"Hello, {name}!")

@workflow
def hello_workflow(name: str):
    say_hello(name=name)
```

### File I/O with FlyteFile

```python
import flyte_migrate  # noqa: F401, I001

from flytekit import task, workflow
from flytekit.types.file import FlyteFile

@task
def write_data(data: str) -> FlyteFile:
    with open("/tmp/output.csv", "w") as f:
        f.write(data)
    return FlyteFile("/tmp/output.csv")

@task
def read_data(ff: FlyteFile) -> str:
    with open(ff, "r") as f:
        return f.read()

@workflow
def file_wf(data: str = "hello") -> str:
    ff = write_data(data=data)
    return read_data(ff=ff)
```

### Conditional Workflow

```python
import flyte_migrate  # noqa: F401, I001

from flytekit import conditional, task, workflow

@task
def is_positive(n: float) -> bool:
    return n > 0

@task
def square(n: float) -> float:
    return n * n

@task
def double(n: float) -> float:
    return n * 2

@workflow
def conditional_wf(n: float) -> float:
    return (
        conditional("check")
        .if_(is_positive(n=n).is_true())
        .then(square(n=n))
        .else_()
        .then(double(n=n))
    )
```

### Nested Workflows

```python
import flyte_migrate  # noqa: F401, I001

from flytekit import task, workflow

@task
def compute_mean(data: list[float]) -> float:
    return sum(data) / len(data)

@workflow
def analyze(source: str) -> float:
    data = fetch_data(source=source)
    return compute_mean(data=data)

@workflow
def parent_wf() -> str:
    mean_a = analyze(source="sensor_a")
    mean_b = analyze(source="sensor_b")
    return combine(mean_a=mean_a, mean_b=mean_b)
```

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
| | `conditional` | Supported | `conditional_example.py` |
| | `LaunchPlan` | Supported | `launchplan_example.py` |
| | Nested workflows | Supported | `nested_workflow_example.py` |
| **Plugins** | Ray (`RayJobConfig`) | Supported | `ray_example.py` |
| | Spark (`Spark`) | Supported | `spark_example.py` |
| **Context** | `current_context()` | Supported | `spark_example.py` |
| | `spark_session` | Supported | `spark_example.py` |

### Not Yet Supported

| API | Notes |
|-----|-------|
| `PodTemplate` | Stubbed (returns None) |
| `reference_task` / `reference_workflow` | Not yet implemented |
| `ContainerTask` | Not yet implemented |
| `approve` / `wait_for_input` | Not yet implemented |
| `StructuredDataset` | Not yet tested |

## How it works

`flyte-migrate` uses Python's import system to intercept v1 API calls and transparently convert them to v2 equivalents. The conversion happens at import time, so there's no runtime overhead.

Under the hood, it:
1. Patches `flytekit` decorators (`@task`, `@workflow`, `@dynamic`)
2. Translates v1 configuration objects to v2 `TaskEnvironment` and `WorkflowEnvironment`
3. Maps plugin configurations to v2 plugin system
4. Handles resource specifications and container images

## Requirements

- Python 3.10+
- `flyte` (v2 SDK)
- `flytekit` (for compatibility)

## Migration Path

1. **Install** `flyte-migrate` in your environment
2. **Add** the import to your v1 workflows
3. **Test** your workflows on Flyte v2
4. **Gradually refactor** to native v2 code when ready (optional)

You can keep using `flyte-migrate` indefinitely, or use it as a bridge while you refactor to native v2 code at your own pace.

## Contributing

Contributions are welcome! Please check the [issues](../../issues) for open tasks or submit a pull request.

## License

Apache License 2.0

## Support

- **Documentation**: [Flyte Documentation](https://docs.flyte.org/)
- **Issues**: [GitHub Issues](../../issues)
- **Community**: [Flyte Slack](https://flyte.org/slack)

---

**Made with love by the Flyte community**
