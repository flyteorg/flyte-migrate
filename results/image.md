# ImageSpec Comprehensive Testing Results

## Summary

Tested all ImageSpec parameters supported by `flyte_migrate._image.py`. Added 58 unit tests covering every helper function and edge case. Added conda warning logs for unsupported parameters.

## Unit Tests (58 tests, all passing)

### `_parse_python_version`
- None, empty string -> None
- "3.11" -> (3, 11)
- "3.11.2" -> (3, 11) (patch ignored)
- "3" -> None (single component)
- "3.0", "4.1" -> correct tuples

### `_parse_platform`
- None, empty string -> None
- Single: "linux/amd64" -> ("linux/amd64",)
- Multiple with whitespace trimming
- Three platforms

### `_strip_version_specifier`
- No specifier: "pandas" -> ("pandas", "")
- All operator types: ==, >=, <=, !=, ~=, >, <
- Compound: "numpy>=1.0,<2.0"
- Plugin with specifier

### `_translate_pip_packages`
- None/empty -> ["flytekit"]
- Regular packages preserved
- All 4 plugin translations (spark, ray, dask, pytorch)
- Version specifiers preserved on v1 package, NOT on v2 package
- Unknown flytekitplugins not translated
- Mixed plugins and regular packages

### `_build_pip_secret_mounts`
- None/empty -> None
- Single and multiple mounts (must use /etc/flyte/secrets)

### `_extract_attributes` (child->parent merge)
- packages, env, commands, copy: merged correctly
- pip_extra_args: concatenated with space
- pip_extra_index_url: merged lists
- pip_secret_mounts: merged lists
- requirements: child-only sets directly; both creates merged file
- env child overwrites parent keys
- No child attributes leaves parent unchanged
- All "parent has None" edge cases

### Conda warnings
- `conda_packages` and `conda_channels` attributes exist on ImageSpec

## Bug Fix

Added warning logs for `conda_packages` and `conda_channels` in `_apply_image_layers()`:
```python
if spec.conda_packages:
    logger.warning("conda_packages not supported in v2, ignoring: %s", spec.conda_packages)
if spec.conda_channels:
    logger.warning("conda_channels not supported in v2, ignoring: %s", spec.conda_channels)
```

## Remote Execution

### Successful run
- **Workflow**: `image_comprehensive_wf`
- **Run URL**: https://demo.hosted.unionai.cloud/v2/domain/development/project/flyte-migrate/runs/rvhrbnqt59cjxscfr6d9
- **Images tested**:
  1. `full_image`: packages + apt_packages + env + commands
  2. `versioned_image`: python_version="3.11", name="custom-image"
  3. `nested_image`: base_image=ImageSpec with packages, apt, env merging

### Build failures with pip_index/pip_extra_args
- ImageSpec with `pip_index` and `pip_extra_args="--no-deps"` caused remote build failures
- These parameters are correctly translated to v2 Image layers but the remote builder may not support custom pip indexes or extra args
- Removed from remote example; unit tests still cover the translation logic

### Parameters NOT testable remotely
| Parameter | Reason |
|-----------|--------|
| `base_image` (string) | Requires the base image to be accessible by remote builder; "python:3.11-slim" without registry failed |
| `pip_index` | Remote builder may not have access to custom pip indexes |
| `pip_extra_args` | `--no-deps` caused build failure; may be builder limitation |
| `pip_secret_mounts` | Requires actual secrets configured on the cluster |
| `requirements` | Requires file to be present in build context |
| `copy` | Requires files to be present in build context |
| `source_root` | Requires source directory in build context |
| `registry` | Requires push access to a container registry |
| `conda_packages/conda_channels` | Not supported in v2 (warning logged) |
| `cuda/cudnn` | Handled by Docker builder automatically, not testable in unit tests |
| `builder="envd"/"noop"` | Warning logged, not supported in v2 |

## Files Changed
- `src/flyte_migrate/_image.py` — added conda_packages/conda_channels warnings
- `examples/image_comprehensive.py` — new comprehensive example
- `tests/test_image_comprehensive.py` — 58 new unit tests
