"""Tests for Ray and PyTorch plugin transformers."""

import flyte
import flytekit

import flyte_migrate  # noqa: F401 — triggers patching
from flyte_migrate._plugins import _transform_plugin_config_v1_to_v2
from flyte_migrate._plugins.pytorch import _transform_pytorch_config_v1_to_v2
from flyte_migrate._plugins.ray import _transform_ray_config_v1_to_v2

# ---------------------------------------------------------------------------
# Ray plugin
# ---------------------------------------------------------------------------


class TestRayWorkerNodeConfig:
    def test_single_worker_group(self):
        from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[
                WorkerNodeConfig(group_name="default", replicas=3),
            ],
        )
        result = _transform_ray_config_v1_to_v2(v1)
        assert result is not None
        assert len(result.worker_node_config) == 1
        w = result.worker_node_config[0]
        assert w.group_name == "default"
        assert w.replicas == 3

    def test_multiple_worker_groups(self):
        from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[
                WorkerNodeConfig(group_name="cpu-workers", replicas=4),
                WorkerNodeConfig(group_name="gpu-workers", replicas=2),
            ],
        )
        result = _transform_ray_config_v1_to_v2(v1)
        assert len(result.worker_node_config) == 2
        assert result.worker_node_config[0].group_name == "cpu-workers"
        assert result.worker_node_config[0].replicas == 4
        assert result.worker_node_config[1].group_name == "gpu-workers"
        assert result.worker_node_config[1].replicas == 2

    def test_worker_with_autoscaling(self):
        from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[
                WorkerNodeConfig(
                    group_name="scalable",
                    replicas=2,
                    min_replicas=1,
                    max_replicas=10,
                ),
            ],
            enable_autoscaling=True,
        )
        result = _transform_ray_config_v1_to_v2(v1)
        assert result.enable_autoscaling is True
        w = result.worker_node_config[0]
        assert w.min_replicas == 1
        assert w.max_replicas == 10

    def test_worker_with_ray_start_params(self):
        from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[
                WorkerNodeConfig(
                    group_name="custom",
                    replicas=1,
                    ray_start_params={"num-cpus": "4", "num-gpus": "1"},
                ),
            ],
        )
        result = _transform_ray_config_v1_to_v2(v1)
        w = result.worker_node_config[0]
        assert w.ray_start_params == {"num-cpus": "4", "num-gpus": "1"}

    def test_worker_with_resources(self):
        from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[
                WorkerNodeConfig(
                    group_name="resourced",
                    replicas=2,
                    requests=flytekit.Resources(cpu="2", mem="4Gi"),
                    limits=flytekit.Resources(cpu="4", mem="8Gi"),
                ),
            ],
        )
        result = _transform_ray_config_v1_to_v2(v1)
        w = result.worker_node_config[0]
        assert isinstance(w.requests, flyte.Resources)
        assert isinstance(w.limits, flyte.Resources)

    def test_worker_with_pod_template(self):
        from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

        v1_pod = flytekit.PodTemplate(
            primary_container_name="ray-worker",
            labels={"tier": "compute"},
        )
        v1 = RayJobConfig(
            worker_node_config=[
                WorkerNodeConfig(group_name="podded", replicas=1, pod_template=v1_pod),
            ],
        )
        result = _transform_ray_config_v1_to_v2(v1)
        w = result.worker_node_config[0]
        assert isinstance(w.pod_template, flyte.PodTemplate)
        assert w.pod_template.primary_container_name == "ray-worker"
        assert w.pod_template.labels == {"tier": "compute"}


class TestRayHeadNodeConfig:
    def test_no_head_node(self):
        from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[WorkerNodeConfig(group_name="g", replicas=1)],
        )
        result = _transform_ray_config_v1_to_v2(v1)
        assert result.head_node_config is None

    def test_head_node_with_ray_start_params(self):
        from flytekitplugins.ray import HeadNodeConfig, RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[WorkerNodeConfig(group_name="g", replicas=1)],
            head_node_config=HeadNodeConfig(
                ray_start_params={"log-color": "True", "num-cpus": "0"},
            ),
        )
        result = _transform_ray_config_v1_to_v2(v1)
        assert result.head_node_config is not None
        assert result.head_node_config.ray_start_params == {"log-color": "True", "num-cpus": "0"}

    def test_head_node_with_resources(self):
        from flytekitplugins.ray import HeadNodeConfig, RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[WorkerNodeConfig(group_name="g", replicas=1)],
            head_node_config=HeadNodeConfig(
                requests=flytekit.Resources(cpu="1", mem="2Gi"),
                limits=flytekit.Resources(cpu="2", mem="4Gi"),
            ),
        )
        result = _transform_ray_config_v1_to_v2(v1)
        h = result.head_node_config
        assert isinstance(h.requests, flyte.Resources)
        assert isinstance(h.limits, flyte.Resources)

    def test_head_node_with_pod_template(self):
        from flytekitplugins.ray import HeadNodeConfig, RayJobConfig, WorkerNodeConfig

        v1_pod = flytekit.PodTemplate(
            primary_container_name="ray-head",
            annotations={"prometheus.io/scrape": "true"},
        )
        v1 = RayJobConfig(
            worker_node_config=[WorkerNodeConfig(group_name="g", replicas=1)],
            head_node_config=HeadNodeConfig(pod_template=v1_pod),
        )
        result = _transform_ray_config_v1_to_v2(v1)
        h = result.head_node_config
        assert isinstance(h.pod_template, flyte.PodTemplate)
        assert h.pod_template.primary_container_name == "ray-head"


class TestRayJobConfigTopLevel:
    def test_runtime_env(self):
        from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[WorkerNodeConfig(group_name="g", replicas=1)],
            runtime_env={"pip": ["numpy", "pandas"], "env_vars": {"MY_VAR": "1"}},
        )
        result = _transform_ray_config_v1_to_v2(v1)
        assert result.runtime_env == {"pip": ["numpy", "pandas"], "env_vars": {"MY_VAR": "1"}}

    def test_address(self):
        from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[WorkerNodeConfig(group_name="g", replicas=1)],
            address="ray://ray-head:10001",
        )
        result = _transform_ray_config_v1_to_v2(v1)
        assert result.address == "ray://ray-head:10001"

    def test_shutdown_and_ttl(self):
        from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[WorkerNodeConfig(group_name="g", replicas=1)],
            shutdown_after_job_finishes=True,
            ttl_seconds_after_finished=300,
        )
        result = _transform_ray_config_v1_to_v2(v1)
        assert result.shutdown_after_job_finishes is True
        assert result.ttl_seconds_after_finished == 300

    def test_enable_autoscaling_default_false(self):
        from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[WorkerNodeConfig(group_name="g", replicas=1)],
        )
        result = _transform_ray_config_v1_to_v2(v1)
        assert result.enable_autoscaling is False

    def test_non_ray_config_returns_none(self):
        result = _transform_ray_config_v1_to_v2("not a ray config")
        assert result is None

    def test_full_config(self):
        """Smoke test: all parameters together."""
        from flytekitplugins.ray import HeadNodeConfig, RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[
                WorkerNodeConfig(
                    group_name="cpu-pool",
                    replicas=4,
                    min_replicas=2,
                    max_replicas=8,
                    ray_start_params={"num-cpus": "4"},
                    requests=flytekit.Resources(cpu="2", mem="4Gi"),
                    limits=flytekit.Resources(cpu="4", mem="8Gi"),
                ),
                WorkerNodeConfig(
                    group_name="gpu-pool",
                    replicas=2,
                    min_replicas=1,
                    max_replicas=4,
                    ray_start_params={"num-gpus": "1"},
                ),
            ],
            head_node_config=HeadNodeConfig(
                ray_start_params={"log-color": "True", "num-cpus": "0"},
                requests=flytekit.Resources(cpu="1", mem="2Gi"),
            ),
            enable_autoscaling=True,
            runtime_env={"pip": ["torch"]},
            shutdown_after_job_finishes=True,
            ttl_seconds_after_finished=600,
        )
        result = _transform_ray_config_v1_to_v2(v1)
        assert result is not None
        assert len(result.worker_node_config) == 2
        assert result.head_node_config is not None
        assert result.enable_autoscaling is True
        assert result.runtime_env == {"pip": ["torch"]}
        assert result.shutdown_after_job_finishes is True
        assert result.ttl_seconds_after_finished == 600


class TestRayViaPluginDispatch:
    def test_dispatch_routes_to_ray_transformer(self):
        from flytekitplugins.ray import RayJobConfig, WorkerNodeConfig

        v1 = RayJobConfig(
            worker_node_config=[WorkerNodeConfig(group_name="g", replicas=1)],
        )
        result = _transform_plugin_config_v1_to_v2(v1)
        assert result is not None
        assert len(result.worker_node_config) == 1


# ---------------------------------------------------------------------------
# PyTorch plugin
# ---------------------------------------------------------------------------


class TestPyTorchElasticConfig:
    def test_basic_elastic(self):
        from flytekitplugins.kfpytorch import Elastic

        v1 = Elastic(nnodes=1, nproc_per_node=2)
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result is not None
        assert result.nnodes == 1
        assert result.nproc_per_node == 2

    def test_multi_node(self):
        from flytekitplugins.kfpytorch import Elastic

        v1 = Elastic(nnodes=4, nproc_per_node=8)
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.nnodes == 4
        assert result.nproc_per_node == 8

    def test_nnodes_range_string(self):
        from flytekitplugins.kfpytorch import Elastic

        v1 = Elastic(nnodes="1:4", nproc_per_node=2)
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.nnodes == "1:4"

    def test_monitor_interval(self):
        from flytekitplugins.kfpytorch import Elastic

        v1 = Elastic(nnodes=1, nproc_per_node=1, monitor_interval=10)
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.monitor_interval == 10

    def test_max_restarts(self):
        from flytekitplugins.kfpytorch import Elastic

        v1 = Elastic(nnodes=1, nproc_per_node=1, max_restarts=5)
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.max_restarts == 5

    def test_rdzv_configs(self):
        from flytekitplugins.kfpytorch import Elastic

        rdzv = {"timeout": "60000", "join_timeout": "30000"}
        v1 = Elastic(nnodes=1, nproc_per_node=1, rdzv_configs=rdzv)
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.rdzv_configs == {"timeout": "60000", "join_timeout": "30000"}

    def test_no_run_policy(self):
        from flytekitplugins.kfpytorch import Elastic

        v1 = Elastic(nnodes=1, nproc_per_node=1)
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.run_policy is None

    def test_non_elastic_config_returns_none(self):
        result = _transform_pytorch_config_v1_to_v2("not elastic")
        assert result is None


class TestRunPolicy:
    def test_clean_pod_policy_all(self):
        from flytekitplugins.kfpytorch import CleanPodPolicy, Elastic, RunPolicy

        v1 = Elastic(
            nnodes=1,
            nproc_per_node=1,
            run_policy=RunPolicy(clean_pod_policy=CleanPodPolicy.ALL),
        )
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.run_policy is not None
        assert result.run_policy.clean_pod_policy == "ALL"

    def test_clean_pod_policy_none_enum(self):
        from flytekitplugins.kfpytorch import CleanPodPolicy, Elastic, RunPolicy

        v1 = Elastic(
            nnodes=1,
            nproc_per_node=1,
            run_policy=RunPolicy(clean_pod_policy=CleanPodPolicy.NONE),
        )
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.run_policy is not None
        assert result.run_policy.clean_pod_policy == "NONE"

    def test_clean_pod_policy_running(self):
        from flytekitplugins.kfpytorch import CleanPodPolicy, Elastic, RunPolicy

        v1 = Elastic(
            nnodes=1,
            nproc_per_node=1,
            run_policy=RunPolicy(clean_pod_policy=CleanPodPolicy.RUNNING),
        )
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.run_policy is not None
        assert result.run_policy.clean_pod_policy == "RUNNING"

    def test_ttl_seconds_after_finished(self):
        from flytekitplugins.kfpytorch import CleanPodPolicy, Elastic, RunPolicy

        v1 = Elastic(
            nnodes=1,
            nproc_per_node=1,
            run_policy=RunPolicy(
                clean_pod_policy=CleanPodPolicy.ALL,
                ttl_seconds_after_finished=3600,
            ),
        )
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.run_policy.ttl_seconds_after_finished == 3600

    def test_active_deadline_seconds(self):
        from flytekitplugins.kfpytorch import CleanPodPolicy, Elastic, RunPolicy

        v1 = Elastic(
            nnodes=1,
            nproc_per_node=1,
            run_policy=RunPolicy(
                clean_pod_policy=CleanPodPolicy.ALL,
                active_deadline_seconds=7200,
            ),
        )
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.run_policy.active_deadline_seconds == 7200

    def test_backoff_limit(self):
        from flytekitplugins.kfpytorch import CleanPodPolicy, Elastic, RunPolicy

        v1 = Elastic(
            nnodes=1,
            nproc_per_node=1,
            run_policy=RunPolicy(
                clean_pod_policy=CleanPodPolicy.ALL,
                backoff_limit=3,
            ),
        )
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.run_policy.backoff_limit == 3

    def test_full_run_policy(self):
        from flytekitplugins.kfpytorch import CleanPodPolicy, Elastic, RunPolicy

        v1 = Elastic(
            nnodes=2,
            nproc_per_node=4,
            max_restarts=3,
            monitor_interval=15,
            rdzv_configs={"timeout": "30000"},
            run_policy=RunPolicy(
                clean_pod_policy=CleanPodPolicy.RUNNING,
                ttl_seconds_after_finished=1800,
                active_deadline_seconds=3600,
                backoff_limit=5,
            ),
        )
        result = _transform_pytorch_config_v1_to_v2(v1)
        assert result.nnodes == 2
        assert result.nproc_per_node == 4
        assert result.max_restarts == 3
        assert result.monitor_interval == 15
        assert result.rdzv_configs == {"timeout": "30000"}
        rp = result.run_policy
        assert rp.clean_pod_policy == "RUNNING"
        assert rp.ttl_seconds_after_finished == 1800
        assert rp.active_deadline_seconds == 3600
        assert rp.backoff_limit == 5

    def test_run_policy_with_none_clean_pod_policy(self):
        """RunPolicy with clean_pod_policy=None should result in no run_policy on v2."""
        from flytekitplugins.kfpytorch import Elastic, RunPolicy

        v1 = Elastic(
            nnodes=1,
            nproc_per_node=1,
            run_policy=RunPolicy(ttl_seconds_after_finished=600),
        )
        result = _transform_pytorch_config_v1_to_v2(v1)
        # The transformer only creates run_policy when clean_pod_policy is not None
        assert result.run_policy is None


class TestPyTorchViaPluginDispatch:
    def test_dispatch_routes_to_pytorch_transformer(self):
        from flytekitplugins.kfpytorch import Elastic

        v1 = Elastic(nnodes=1, nproc_per_node=1)
        result = _transform_plugin_config_v1_to_v2(v1)
        assert result is not None
        assert result.nnodes == 1
