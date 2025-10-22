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

### Map Task

```python
import flyte_migrate  # noqa: F401, I001
import functools

from flytekit import map_task, task, workflow

@task
def calculate_price(quantity: int, price: float, shipping: float) -> float:
    return quantity * price * shipping

@workflow
def batch_pricing(quantities: list[int], price: float, shipping: float) -> list[float]:
    partial_task = functools.partial(calculate_price, price=price, shipping=shipping)
    return map_task(partial_task)(quantities)
```

### Ray Plugin

```python
import flyte_migrate  # noqa: F401, I001

import ray
from flytekit import task, workflow, Resources, ImageSpec
from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

image = ImageSpec(packages=["flytekitplugins-ray"])

@ray.remote
def compute(x):
    return x * x

@task(
    task_config=RayJobConfig(
        worker_node_config=[WorkerNodeConfig(group_name="workers", replicas=2)]
    ),
    limits=Resources(mem="2Gi"),
    container_image=image,
)
def ray_task() -> list[int]:
    futures = [compute.remote(i) for i in range(10)]
    return ray.get(futures)

@workflow
def ray_workflow() -> list[int]:
    return ray_task()
```

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
