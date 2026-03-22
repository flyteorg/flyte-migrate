# Control Flow Testing Results

## map_task

### concurrency
- **Status**: SUPPORTED in v2
- **Details**: `flyte.map()` accepts `concurrency: int = 0` natively. Updated `MapShim` to forward this parameter when set.
- **v1 API**: `map_task(task, concurrency=5)`
- **v2 API**: `flyte.map(task, *args, concurrency=5)`

### min_successes / min_success_ratio
- **Status**: NOT SUPPORTED in v2
- **Details**: `flyte.map()` does not accept `min_successes` or `min_success_ratio`. The `MapShim` accepts these for v1 API compatibility but does not forward them.
- **Migration note**: Users relying on partial success semantics will need to handle failures via `return_exceptions=True` (which is the default in `flyte.map()`) and implement their own success-ratio logic.

### functools.partial
- **Status**: WORKS — `flyte.map()` accepts `functools.partial` as the target function.

## LaunchPlan

### CronSchedule
- **Status**: WORKS — Converted to `Trigger` with `Cron` automation.

### FixedRate
- **Status**: WORKS — Converted to `Trigger` with `FixedRate` automation.

### default_inputs / fixed_inputs
- **Status**: WORKS — Merged via `merge_inputs()` and passed to `Trigger.inputs`. Fixed inputs override defaults.

### auto_activate
- **Status**: WORKS — Forwarded to `Trigger.auto_activate`.

### get_or_create()
- **Status**: WORKS — Alias for `create()`.

### labels / annotations
- **Status**: WORKS — Converted from v1 `Labels`/`Annotations` models to plain dicts.

### overwrite_cache
- **Status**: WORKS — Forwarded to `Trigger.overwrite_cache`.

## @dynamic

- **Status**: WORKS — Delegates to `task_shim`, which produces a regular v2 task. Dynamic tasks that spawn subtasks or other dynamics work correctly.

## Subworkflows

- **Status**: WORKS — In v2, workflows are tasks, so calling one workflow from another is a normal function call. No special handling needed.

## Nested Dynamic

- **Status**: WORKS — A dynamic task spawning another dynamic task functions correctly since both are regular v2 tasks.

## v1 conditional() Migration Note

v1 `flytekit.conditional()` is NOT shimmed. Users should replace `conditional()` with native Python `if/elif/else` statements, which is the idiomatic v2 approach. Since v2 workflows are plain Python functions, branching logic works naturally without a special conditional API. See `examples/conditional_wf.py` for a reference pattern.
