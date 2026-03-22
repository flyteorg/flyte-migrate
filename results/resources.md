# Resource Comprehensive Test Results

**Date**: 2026-03-22
**Run ID**: r9vxgw994jssfxjzfcff
**URL**: https://demo.hosted.unionai.cloud/v2/domain/development/project/flyte-migrate/runs/r9vxgw994jssfxjzfcff
**Status**: SUCCEEDED

## Tasks Tested

| Task | Resource Config | Result |
|------|----------------|--------|
| `task_requests_only` | `requests=Resources(cpu="1", mem="512Mi")` | PASSED |
| `task_limits_only` | `limits=Resources(cpu="2", mem="1Gi")` | PASSED |
| `task_requests_and_limits` | `requests=Resources(cpu="1", mem="512Mi"), limits=Resources(cpu="2", mem="1Gi")` | PASSED |
| `task_resources_param` | `resources=Resources(cpu="1", mem="1Gi")` | PASSED |
| `task_shared_memory_true` | `requests=..., shared_memory=True` | PASSED |
| `task_shared_memory_explicit` | `requests=..., shared_memory="2Gi"` | PASSED |
| `task_ephemeral_storage` | `requests=Resources(cpu="1", mem="512Mi", ephemeral_storage="5Gi")` | PASSED |

## GPU Tasks - Skipped

GPU count-only (`gpu="1"`) was **not** included in the workflow because v2 `flyte.Resources`
validates the GPU field against a known set of accelerator literals (e.g., `"T4:1"`, `"A100:2"`).
The v1 pattern of `gpu="1"` (count-only without a named accelerator) produces the string `"1"`
via `_format_gpu`, which v2 rejects at **definition time** with a `ValueError`.

### Compatibility gap

The shim's `_format_gpu` function returns a bare count string when no accelerator is provided.
V2 requires a named accelerator from the `Accelerators` literal type. This means:

- `gpu="1"` alone (v1 pattern) -> fails in v2
- `accelerator=T4` with `gpu="1"` -> produces `"T4:1"` -> works in v2
- `accelerator=T4` alone -> produces `"T4"` -> works in v2

**Recommendation**: Users migrating GPU tasks must add the `accelerator` parameter, or the shim
should map bare GPU counts to a default accelerator.

## Unit Tests

39 tests added in `tests/test_resource_comprehensive.py`, all passing. Coverage includes:

- requests-only (cpu, mem, individual fields)
- limits-only
- requests + limits merged into tuples
- `resources` param alone
- `resources` + `requests` mutual exclusion error
- GPU formatting (`_format_gpu`) with accelerator, count, both
- End-to-end GPU through `_transform_resource_v1_to_v2` with valid v2 accelerator names
- `shared_memory` conversion (True -> "auto", string passthrough)
- `ephemeral_storage` -> `disk` mapping
- Edge cases: empty resources, no args, all fields combined
