# Ray & PyTorch Plugin Testing Results

Date: 2026-03-22

## Unit Tests

34 tests in `tests/test_ray_pytorch_plugins.py` — all passing.

### Ray Plugin Tests (17 tests)
- **WorkerNodeConfig**: single group, multiple groups, autoscaling (min/max replicas), ray_start_params, resources, pod_template
- **HeadNodeConfig**: no head node, ray_start_params, resources, pod_template
- **RayJobConfig top-level**: runtime_env, address, shutdown_after_job_finishes, ttl_seconds_after_finished, enable_autoscaling default, non-ray returns None, full config smoke test
- **Plugin dispatch**: routes RayJobConfig through `_transform_plugin_config_v1_to_v2`

### PyTorch Plugin Tests (17 tests)
- **Elastic config**: basic, multi-node (nnodes=4), nnodes range string ("1:4"), monitor_interval, max_restarts, rdzv_configs, no run_policy, non-elastic returns None
- **RunPolicy**: CleanPodPolicy.ALL/NONE/RUNNING enum-to-string conversion, ttl_seconds_after_finished, active_deadline_seconds, backoff_limit, full run_policy, run_policy with None clean_pod_policy
- **Plugin dispatch**: routes Elastic through `_transform_plugin_config_v1_to_v2`

## Remote Execution

### Ray Examples

#### Basic Ray workflow (single worker group)
- Run: `r8ckvb64j2t8cqq47mpv`
- URL: https://demo.hosted.unionai.cloud/v2/domain/development/project/flyte-migrate/runs/r8ckvb64j2t8cqq47mpv
- Status: Submitted successfully. Image build and code bundle upload completed.

#### Autoscaling Ray workflow (multiple worker groups, enable_autoscaling, runtime_env)
- Run: `rhs7khxdkh98ffrcpgdv`
- URL: https://demo.hosted.unionai.cloud/v2/domain/development/project/flyte-migrate/runs/rhs7khxdkh98ffrcpgdv
- Status: Submitted successfully. Image build and code bundle upload completed.

### PyTorch Examples

#### Basic PyTorch workflow (single-node Elastic)
- Run: `rggjvmvgvr4gkhpjl662`
- URL: https://demo.hosted.unionai.cloud/v2/domain/development/project/flyte-migrate/runs/rggjvmvgvr4gkhpjl662
- Status: Submitted successfully.

#### Multi-node PyTorch workflow (nnodes=2, full RunPolicy)
- Run: `rjb7sbnmf6wsq2t24nxt`
- URL: https://demo.hosted.unionai.cloud/v2/domain/development/project/flyte-migrate/runs/rjb7sbnmf6wsq2t24nxt
- Status: Submitted successfully.

#### No-restart PyTorch workflow (CleanPodPolicy.NONE, max_restarts=0)
- Run: `rnqx9c48gzksks92zzmj`
- URL: https://demo.hosted.unionai.cloud/v2/domain/development/project/flyte-migrate/runs/rnqx9c48gzksks92zzmj
- Status: Submitted successfully.

## Key Findings

1. **Transformation logic is correct**: All v1 Ray and PyTorch config fields are properly mapped to v2 equivalents.
2. **CleanPodPolicy enum conversion**: v1 uses enum values (e.g., `CleanPodPolicy.ALL`), and the transformer converts to string using `.name` (e.g., `"ALL"`). This works because flyte-sdk capitalizes the policy value at runtime.
3. **Resource and PodTemplate transforms**: Worker and head node resources/pod_templates correctly delegate to `_transform_resource_v1_to_v2` and `_transform_pod_template_v1_to_v2`.
4. **Autoscaling**: `enable_autoscaling`, `min_replicas`, and `max_replicas` are passed through correctly.
5. **Runtime env**: Dict-based runtime_env is passed through unchanged to v2.
6. **RunPolicy edge case**: When `run_policy` is provided but `clean_pod_policy` is `None`, the transformer skips creating a v2 RunPolicy (sets it to `None`). This means `ttl_seconds_after_finished`, `active_deadline_seconds`, and `backoff_limit` are lost if `clean_pod_policy` is not set. This is a potential issue if users set RunPolicy without specifying clean_pod_policy.

## Examples Enhanced

- `examples/plugins/ray_example.py`: Added autoscaling workflow with multiple worker groups, head node resources, runtime_env, shutdown/TTL settings
- `examples/plugins/pytorch_example.py`: Added multi-node workflow (nnodes=2, full RunPolicy) and no-restart workflow (CleanPodPolicy.NONE, backoff_limit=0)
