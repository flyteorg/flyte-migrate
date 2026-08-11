# Flyte v2 SDK: Capabilities and Gaps

## Summary

Flyte v2 is a **fundamentally redesigned** SDK that shifts from imperative workflow orchestration to purely functional/pythonic execution. Here's what works, what's limited, and what's missing.

---

## ✅ V2 Capabilities

### Core Task/Workflow Features

| Feature | v2 Status | Notes |
|---------|-----------|-------|
| `@task` decorator | ✅ Full support | Python async/sync functions; TaskTemplate-based |
| `@workflow` decorator | ✅ Full support | Workflows are plain Python functions |
| Subworkflows | ✅ Full support | Workflows calling workflows; typed I/O |
| `@dynamic` tasks | ✅ Full support | Python loops generate subtasks at runtime |
| `map()` | ✅ Full support | `flyte.map()` wraps list iteration; supports structured datasets |
| Return types | ✅ Full support | Primitives (int, float, str, bool), List, Dict, Optional, NamedTuple, Dataclass, custom types |
| FlyteFile / FlyteDirectory | ✅ Full support | In `flyte.io` module; `File` and `Dir` classes |
| StructuredDataset | ✅ Full support | Typed columnar I/O; pandas DataFrame support via transformers |

### Task Configuration

| Feature | v2 Status | Notes |
|---------|-----------|-------|
| Caching | ✅ Full support | `cache` param: "auto", "override", "disable", or `Cache` object |
| Retries | ✅ Full support | `retries` param (int) or `RetryStrategy` object with exponential backoff |
| Timeout | ✅ Full support | At task level (`timeout` param); timedelta or seconds |
| Resource requests/limits | ✅ Full support | `Resources(cpu=..., memory=..., gpu=..., disk=...)` |
| Environment variables | ✅ Full support | `env_vars` dict or TaskEnvironment-level defaults |
| Secrets | ✅ Full support | `secrets` param; FILE or ENV_VAR mount types |
| Interruptible/Preemptible | ✅ Full support | `interruptible=True` allows spot instances |
| Queue naming | ✅ Full support | `queue` param; routes to specific cluster queues |
| Pod template customization | ✅ Full support | Sidecars, volumes, init containers, affinity rules |
| Container image | ✅ Full support | Docker image string or `Image` object with pip/apt packages, env vars, base image |

### Plugins

| Plugin | v2 Status | Notes |
|--------|-----------|-------|
| **Spark** | ✅ Supported | `SparkConfiguration` config; driver/executor pod templates |
| **Ray** | ✅ Supported | `RayJobConfiguration` config; head/worker node configs with autoscaling |
| **Dask** | ✅ Supported | `DaskConfiguration` config; worker cluster specification |
| **PyTorch** | ✅ Supported | `PyTorchConfiguration` config; multi-node distributed training |
| **BigQuery** | ✅ Supported | Agent-based task; SQL dialect support; project/location config |
| **Raw Container** | ✅ Supported | `ContainerTask` in `flyte.extras`; arbitrary shell commands + I/O binding |

### Scheduling & Triggering

| Feature | v2 Status | Notes |
|---------|-----------|-------|
| Cron schedules | ✅ Full support | `flyte.Cron(...)` trigger object |
| Fixed-rate schedules | ✅ Full support | `flyte.FixedRate(...)` trigger object |
| Trigger association | ✅ Full support | `triggers` param on `@env.task` or `.override()` |

### Execution & Deployment

| Feature | v2 Status | Notes |
|---------|-----------|-------|
| Local execution | ✅ Full support | `python examples/example.py` or local test runner |
| Remote execution | ✅ Full support | v2 Flyte cluster required; `flyte.run()` with `mode="remote"` |
| Task environment | ✅ Full support | Group tasks by image/config; inherit defaults; per-task overrides |
| Reusable environments | ✅ Full support | `ReusePolicy(concurrency, ttl)` for container reuse across invocations |
| Reports (Deck) | ✅ Full support | `flyte.Deck()` + HTML content generation |
| Observability | ✅ Full support | Deck reports, structured logging, metrics |

### Conditionals & Branching

| Feature | v2 Status | Notes |
|---------|-----------|-------|
| Native Python `if/elif/else` | ✅ Full support | Workflows are plain Python → control flow is native; no special API needed |
| Task chaining | ✅ Full support | Sequential task calls; dependencies implicit from Python dataflow |

---

## ⚠️  Limitations & Gaps

### Missing or Severely Limited

| Feature | v1 Equivalent | v2 Status | Workaround |
|---------|----------------|-----------|-----------|
| **Reference Tasks/Workflows** | `reference_task`, `reference_workflow`, `reference_launch_plan` | ✅ Supported | `flyte.remote.TaskDetails.get(...)`; the shim maps all three decorators onto it |
| **SQL Tasks** | `SQLTask` | ⚠️ Partial | BigQuery agent-based only; other SQL engines not directly supported |
| **Sensor Tasks** | `SensorTask` (manual polling) | ❌ Not in v2 SDK | Implement as a polling loop in a task, a custom agent, or an external trigger |
| **Gate/Approval Nodes** | `approve`, `wait_for_input` | ✅ Supported | Shimmed onto `flyte.new_condition(...).wait()`. v2 limitation: condition payloads must be `bool`/`int`/`float`/`str` — v1 `wait_for_input` allowed arbitrary `expected_type`s |
| **Sleep Gate** | `sleep(duration)` | ⚠️ Partial | Shimmed as `time.sleep` in the workflow driver container (already alive for the whole run in shimmed mode); v2's backend `core-sleep` plugin exists if driver time matters |
| **Notifications** | `Notification` on LaunchPlan | ⚠️ Trigger-level only | v2 `flyte.notify` (Email, Slack webhook, Teams, Webhook) attaches to `Trigger`s, not ad-hoc runs; the shim maps v1 email/slack/pagerduty recipients to v2 `Email` |
| **Node-level metadata** | `node_name`, timeout at node level | ⚠️ Partial | Task-level timeout supported; node naming implicit from function names |
| **LaunchPlan** | v1 `LaunchPlan` class | ⚠️ Partial | Converted to `Trigger` objects. No v2 equivalent for `max_parallelism`, `raw_output_data_config`, `security_context`/`auth_role`, `ConcurrencyPolicy`, or artifact-event triggers (`OnArtifact`) |
| **Labels/Annotations on tasks** | `@task(labels=..., annotations=...)` | ❌ Not in v2 SDK | v2 supports labels/annotations only on `Trigger`s; task-level ones are dropped by the shim (logged) |
| **Cache policies** | `Cache(policies=[...])` | ❌ Not in v2 SDK | v1 computes policy-based versions client-side; v2 `Cache` supports `version_override`/`serialize`/`ignored_inputs`/`salt` but not pluggable policies |
| **Workflow failure handling** | `failure_policy`, `on_failure` | ❌ Not in v2 SDK | v2 workflows are plain Python — use `try/except` around task calls |
| **map_task partial success** | `min_successes`, `min_success_ratio` | ⚠️ Client-side | `flyte.map()` returns failures as exceptions (`return_exceptions=True`); the shim enforces the threshold and substitutes `None`, matching v1 semantics |
| **Eager workflows** | `@eager` | ❌ No shim | v2 tasks are already async Python — call tasks with `await` directly; no translation implemented |
| **Custom types** | Type system for domain objects | ✅ Supported | Use dataclasses, NamedTuple, or custom TypeTransformers |
| **Implicit dependency inference** | DAG inferred from code | ✅ Full support | v2 workflows = pure Python; dependencies implicit |

### Node Timeout vs. Task Timeout

- **v2 only has task-level timeout**, not node-level timeout
- A node in v2 = a task execution
- If v1 code relies on node-level timeout distinct from task timeout, this is lost in v2

### Plugin Ecosystem

| Gap | Impact | Workaround |
|-----|--------|-----------|
| Athena SQL agent | v1 had `AthenaTask` | Write custom agent or use BigQuery if available |
| Custom SQL engines | v1 could define SQL task plugins | Use `ContainerTask` to wrap CLI tools or write custom agent |
| Distributed sensors | v1 `SensorTask` with polling | Implement as polling loop in a task or external workflow trigger |

---

## 🔄 Architectural Differences

### v2 is Functional, Not Imperative

| Aspect | v1 | v2 |
|--------|----|----|
| **Control flow** | Special APIs (`conditional`, `map_task`, `dynamic`) | Native Python (`if/elif`, loops, functions) |
| **Branching** | `flytekit.conditional(Predicates)` DSL | Plain `if/elif/else` statements |
| **Looping** | `map_task()` or `dynamic` with imperative loops | Native Python loops in `@dynamic` or `map()` |
| **Subworkflows** | Workflows calling workflows | Same: `@workflow` can call other `@workflow` |
| **Dependency model** | Explicit DAG via special operators | Implicit via Python dataflow (SSA form) |

### TaskEnvironment vs. Task

- **v1**: `@task` is standalone; config per task
- **v2**: `TaskEnvironment` groups tasks by image/config; `@env.task` creates tasks within that environment
- **Impact**: v1 tasks with different images must map to different v2 environments

---

## 📊 v1→v2 Migration Shim Status

The `flyte-migrate` shim bridges v1 APIs to v2:

### Currently Supported

✅ `@task` with v1 config (cache incl. `Cache` objects, retries, timeout, interruptible, resources, accelerators, shared_memory, secrets, env vars, docs, pod templates, plugins, enable_deck)
✅ `@workflow` (converted to v2 task templates; `interruptible` forwarded; v1-only args logged and ignored instead of erroring)
✅ `@dynamic` (converted to v2 orchestrator tasks; same coverage as `@task`)
✅ `map_task` (concurrency forwarded; `min_successes`/`min_success_ratio` enforced client-side with v1 raise/None-fill semantics; `run_all_sub_nodes` inherent — v2 always runs all sub-tasks)
✅ `Deck` (v1 → v2 reports, with end-of-task flush)
✅ `current_context()` (attribute access bridged to v2 `flyte.ctx().data`; common attrs work)
✅ Plugin configs (Spark, Ray, Dask, PyTorch)
✅ `ImageSpec` → `Image` conversion
✅ `Resources` (requests/limits) → v2 `Resources`
✅ `Secret` → v2 `Secret`
✅ `PodTemplate` → v2 `PodTemplate`
✅ `LaunchPlan` → `Trigger` (Cron/FixedRate schedules; default/fixed inputs; labels, annotations, and notifications forwarded; both `create(name, wf)` and v1 `get_or_create(wf)` calling conventions)
✅ `reference_task` / `reference_workflow` / `reference_launch_plan` → v2 remote task references
✅ `FlyteFile` → v2 blob (upload/download type transformer)
✅ `FlyteDirectory` → v2 multipart blob (upload/download type transformer)
✅ `StructuredDataset` → v2 `flyte.io.DataFrame` (type transformer; consumer-side `open()`/`all()`/`iter()` bridged)
✅ `approve` / `wait_for_input` → v2 conditions (`flyte.new_condition(...).wait()`; disapproval raises the v1 `FlyteDisapprovalException`)
✅ `sleep` → sleeps in the workflow driver container
✅ `ContainerTask` → v2 `flyte.extras.ContainerTask` (raw containers; resources, secrets, pod templates, and `TaskMetadata` cache/retries/timeout/interruptible translated)
✅ `BigQueryTask` → v2 agent-based SQL task

### Ignored by the Shim (logged, not errors)

These v1 arguments have no v2 equivalent and are dropped with a warning:

- `@task`: `deprecated`, `execution_mode`, `node_dependency_hints`, `task_resolver`, `disable_deck`, `deck_fields`, `pickle_untyped`, `labels`, `annotations`
- `@workflow`: `failure_policy`, `on_failure`, `docs`, `pickle_untyped`, `default_options`
- `LaunchPlan`: `max_parallelism`, `raw_output_data_config`, `security_context`, `auth_role`, `concurrency`, `trigger` (artifact-event triggers)
- `ContainerTask`: `io_strategy`
- `Cache.policies` (auto/override versioning is used instead)

### Not Yet Supported by Shim

❌ `SensorTask` — no v2 equivalent
❌ `@eager` — v2 tasks are natively async; rewrite as `async def` task
❌ `ShellTask` / SQL tasks other than BigQuery
❌ `FlyteRemote` — use `flyte.remote` v2 APIs
❌ `Artifact` (incl. `OnArtifact` launch plan triggers)
❌ `conditional()` with v1 Predicates DSL — workflows use native Python `if/else` instead
❌ Column-subset projection on `StructuredDataset` (`Annotated[StructuredDataset, kwtypes(...)]` column narrowing)
❌ Node-level timeout (distinct from task timeout)

---

## Conditional Branching in v2

**Important**: v2 workflows are pure Python functions. There is no `flyte.conditional()` API.

### v1 Pattern
```python
@workflow
def wf(x: int) -> int:
    pred = classify(x)
    return conditional("branch").match(
        classify == "positive",
        lambda: double(x),
        classify == "negative",
        lambda: negate(x),
    )
```

### v2 Pattern (via Shim)
```python
@workflow
def wf(x: int) -> int:
    label = classify(x)
    if label == "positive":
        return double(x)
    elif label == "negative":
        return negate(x)
    else:
        return square(x)
```

Since the shim converts v1 workflows to v2 pure Python functions, native `if/elif/else` is the idiomatic approach. The conditional example (`examples/conditional_wf.py`) demonstrates this.

---

## Key Takeaways for Migration

1. **No `SensorTask`, `@eager`, or task-level labels/annotations** — these require custom workarounds or code changes
2. **Gate nodes are shimmed** — `approve`/`wait_for_input` pause the run via v2 conditions (payloads limited to bool/int/float/str); `sleep` runs in the driver container
3. **Conditionals are native Python** — no special DSL needed
4. **Node timeout → Task timeout** — v2 has no separate node-level timeout
5. **Pod templates and plugins are well supported**
6. **FlyteFile/FlyteDirectory are first-class** in v2, and the shim bridges the v1 types across task boundaries
7. **Task environments group by image** — different images must be different environments
8. **Scheduling is via `Trigger` objects**, not `LaunchPlan` — labels, annotations, and (email) notifications survive the translation; execution-config knobs (`max_parallelism`, `security_context`, output location) do not

---

## Testing Recommendations

- **Create examples** for each v1 pattern to verify shim support
- **Test plugins** (Spark, Ray, PyTorch, Dask, BigQuery) with real v2 backend
- **Verify type transformations** for custom types, Dataclasses, NamedTuples
- **Document workarounds** for missing features (sensors, approvals, custom SQL)
- **Validate scheduling** via Cron/FixedRate triggers on v2 backend
