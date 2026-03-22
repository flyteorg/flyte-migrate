# Task Parameters Comprehensive Test Results

## Summary

Tested all `@task` decorator parameters through the flyte-migrate shim (`task_shim`) both locally (unit tests) and on the v2 cluster.

## Parameters Tested

### Working Parameters

| Parameter | v1 Type | v2 Mapping | Status |
|-----------|---------|------------|--------|
| `cache` | `bool` | `"auto"` / `"disable"` | Works |
| `cache_version` | `str` | Accepted, ignored in v2 (no equivalent) | Works (no-op) |
| `retries` | `int` | Passed through to `env.task(retries=...)` | Works |
| `timeout` | `timedelta` / `int` | Passed through to `env.task(timeout=...)` | Works |
| `interruptible` | `bool` | Passed through to `env.task(interruptible=...)` | Works |
| `container_image` | `str` / `ImageSpec` | Transformed via `_transform_image_spec_v1_to_v2` | Works |
| `environment` | `dict` | Mapped to `env_vars` on `TaskEnvironment` | Works |
| `requests` | `Resources` | Merged with limits into v2 `Resources` | Works |
| `limits` | `Resources` | Merged with requests into v2 `Resources` | Works |
| `resources` | `Resources` | Transformed to v2 `Resources` directly | Works |
| `secret_requests` | `list[Secret]` | Transformed via `_transform_secret_v1_to_v2` | Works |
| `docs` | `Documentation` | `short_description` mapped to `description` on `TaskEnvironment` | Works |
| `pod_template` | `PodTemplate` | Transformed via `_transform_pod_template_v1_to_v2` | Works |
| `pod_template_name` | `str` | Passed through as fallback if no pod_template | Works |
| `enable_deck` | `bool` | Mapped to `report=True/False` in `env.task()` | Works |
| `task_config` | plugin config | Dispatched via `_transform_plugin_config_v1_to_v2` | Works |

### Parameters Handled via **kwargs (logged and ignored)

| Parameter | Notes |
|-----------|-------|
| `disable_deck` | Falls to **kwargs; logged as unsupported |
| `execution_mode` | v1-only concept, no v2 equivalent |
| `node_dependency_hints` | v1-only, no v2 equivalent |
| `task_resolver` | v1-only, no v2 equivalent |
| `pickle_untyped` | v1-only, no v2 equivalent |
| `labels` | v1 task-level labels, not supported at task level in v2 (use pod_template) |
| `annotations` | v1 task-level annotations, not supported at task level in v2 (use pod_template) |

## v2 Limitations

1. **`cache_version`**: Accepted by the shim but has no v2 equivalent. v2 caching uses content-based hashing ("auto") rather than explicit versions.
2. **`docs.long_description`**: Only `short_description` is mapped to v2's `description` field. Rich documentation (long_description, source_code) has no direct v2 equivalent.
3. **`disable_deck`**: Not an explicit parameter in the shim; falls to **kwargs. In practice, omitting `enable_deck` or setting it to `False` achieves the same effect.
4. **`accelerator`**: Works in the shim transform but v2 validates GPU strings against a fixed set of `Accelerators`. Custom accelerator strings (e.g., "nvidia-tesla-v100") will fail v2 validation unless they match the v2 Accelerators literal type.

## Unit Tests

14 tests added in `tests/test_task_params.py`:
- `TestTranslateCachePolicy` (2 tests): cache bool to "auto"/"disable"
- `TestBuildTaskEnvironment` (4 tests): docs->description, environment->env_vars, cache mapping
- `TestTaskShim` (8 tests): enable_deck, disable_deck via kwargs, unknown kwargs, cache_version, bare decorator, all params together, docs with long_description

## Cluster Run

- Example: `examples/task_params_comprehensive.py`
- Workflow: `all_task_params_wf` with 8 tasks exercising all parameter categories
- All tasks submitted and executed successfully on the v2 cluster

## No Bugs Found

The existing shim code handles all tested parameters correctly. No code changes were needed in `_task.py`.
