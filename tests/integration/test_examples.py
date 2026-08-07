"""One integration test per example in examples/, run against a real Flyte v2 cluster.

Adding a test is three lines — import the entrypoint and hand it to ``_run_and_wait``:

    def test_hello():
        from examples.hello import wf

        _run_and_wait(wf, name="flyte")

Arguments are ordinary Python objects, so ``priority=Priority.MEDIUM`` and
``dt=datetime(...)`` work as written. The import fails in about a second if the file or
the entrypoint is renamed, or a dependency is missing, instead of after a cluster round
trip.

Examples run in this process. That only works because environment names are namespaced by
defining module (see :mod:`flyte_migrate._workflow`) — six examples define ``wf``, and
under a single shared parent environment importing two of them silently overwrote the
first, then v2 rejected the duplicate environment name outright.

Opt-in only: deselected by default (`addopts = -m 'not integration'`) and skipped without
FLYTE_API_KEY, so the normal `uv run pytest` is unaffected.

    FLYTE_API_KEY=... uv run pytest tests/integration -v -s -m integration
    FLYTE_API_KEY=... uv run pytest tests/integration -v -s -m "integration and not plugins"
    FLYTE_API_KEY=... uv run pytest tests/integration -v -s -m integration -k hello

The `plugins` marker covers examples needing cluster operators (Spark/Ray/Dask/PyTorch) or
external services (BigQuery). The secret examples need an `API_TOKEN` secret in the target
project: `uv run flyte create secret API_TOKEN <value>`.
"""

import os
from pathlib import Path
from typing import Any

import flyte
import pytest
from flyte._code_bundle import build_code_bundle
from flyte.models import ActionPhase

ROOT = Path(__file__).parents[2]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.getenv("FLYTE_API_KEY"), reason="FLYTE_API_KEY not set"),
]


@pytest.fixture(scope="session", autouse=True)
def flyte_client():
    flyte.init_from_api_key(
        project=os.getenv("FLYTE_PROJECT", "flyte-migrate"),
        domain=os.getenv("FLYTE_DOMAIN", "development"),
        image_builder="remote",
        # bundle root = repo root, so src/flyte_migrate ships with the code bundle
        root_dir=ROOT,
    )
    yield flyte


@pytest.fixture(autouse=True)
def _fresh_code_bundle():
    """Each example bundles its own code; a cached bundle would leak between tests."""
    build_code_bundle.cache_clear()


def _run_and_wait(entrypoint: Any, expect: ActionPhase = ActionPhase.SUCCEEDED, **kwargs: Any) -> None:
    run = flyte.with_runcontext(mode="remote").run(entrypoint, **kwargs)
    print(f"\n  {entrypoint.name}\n  {run.url}", flush=True)

    # The watch stream behind wait() is long-lived and the server drops it periodically
    # (RST_STREAM, or UNAVAILABLE "Socket closed"), which says nothing about the run itself.
    # Re-attach rather than reporting a passing run as a failure.
    for attempt in range(3):
        try:
            run.wait(quiet=True)
            break
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  wait() dropped ({type(e).__name__}); re-attaching", flush=True)

    assert run.phase == expect, f"{entrypoint.name} ended {run.phase}, expected {expect} — {run.url}"


def _deploy(deployable: Any) -> None:
    for deployment in flyte.deploy(deployable):
        for env in deployment.envs.values():
            print(f"\n  deployed {env.get_name()}", flush=True)


def _deploy_reference_target() -> None:
    """Register the tasks and launch plans the reference_* examples resolve against.

    They cannot rely on test_deploy_reference_task_target having run: under ``-n`` it may
    land on another worker or run later. Registration is idempotent.
    """
    from examples.reference_task_target import greet_wf

    _deploy(greet_wf.parent_env())


# =============================================================================
# DEPLOYS
# =============================================================================


def test_deploy_reference_task_target():
    _deploy_reference_target()


def test_deploy_launchplan():
    from examples.launchplan import lp

    _deploy(lp)


def test_deploy_launchplan_comprehensive():
    from examples.launchplan_comprehensive import alias_lp

    _deploy(alias_lp)


# =============================================================================
# BASICS
# =============================================================================


def test_hello():
    from examples.hello import wf

    _run_and_wait(wf, name="flyte")


def test_conditional_wf():
    from examples.conditional_wf import conditional_wf

    _run_and_wait(conditional_wf, x=10)


def test_control_flow_comprehensive():
    from examples.control_flow_comprehensive import control_flow_wf

    _run_and_wait(control_flow_wf, data=[1, 2, 3, 4, 5], factor=10, n_dynamic=4)


def test_datatypes_comprehensive():
    from datetime import datetime, timedelta

    from examples.datatypes_comprehensive import Priority, datatypes_wf

    _run_and_wait(
        datatypes_wf,
        values=[1, 2, 3, 4, 5],
        name="Alice",
        age=30,
        score=85.5,
        dt=datetime(2025, 1, 15, 10, 30, 0),
        duration=timedelta(hours=2, minutes=30),
        priority=Priority.MEDIUM,
    )


def test_deck_example():
    from examples.deck_example import wf

    _run_and_wait(wf, name="flyte")


def test_subworkflow_dynamic():
    from examples.subworkflow_dynamic import wf

    _run_and_wait(wf, n=3, name="test")


def test_task_params_comprehensive():
    from examples.task_params_comprehensive import all_task_params_wf

    _run_and_wait(all_task_params_wf, x=5)


# =============================================================================
# EDGE CASES
# =============================================================================


def test_edge_cases_many_tasks():
    from examples.edge_cases import many_tasks_wf

    _run_and_wait(many_tasks_wf, x=0)


def test_edge_cases_single_task():
    from examples.edge_cases import single_task_wf

    _run_and_wait(single_task_wf, x=5)


def test_edge_cases_side_effect():
    from examples.edge_cases import side_effect_wf

    _run_and_wait(side_effect_wf)


def test_edge_cases_long_timeout():
    from examples.edge_cases import long_timeout_wf

    _run_and_wait(long_timeout_wf, x=42)


def test_edge_cases_error():
    """This one raises on purpose — the run is expected to end FAILED."""
    from examples.edge_cases import error_wf

    _run_and_wait(error_wf, expect=ActionPhase.FAILED, x=99)


# =============================================================================
# IMAGES
# =============================================================================


def test_image():
    from examples.image import my_task

    _run_and_wait(my_task)


def test_image_comprehensive():
    from examples.image_comprehensive import image_comprehensive_wf

    _run_and_wait(image_comprehensive_wf)


# =============================================================================
# MAP TASKS
# =============================================================================


def test_map_task():
    from examples.map_task import map_workflow

    _run_and_wait(map_workflow)


def test_map_task_advanced():
    from examples.map_task_advanced import map_task_advanced_wf

    _run_and_wait(map_task_advanced_wf, data=[1, 2, 3, 4, 5])


# =============================================================================
# RESOURCES, POD TEMPLATES, SECRETS
# =============================================================================


def test_resource_comprehensive():
    from examples.resource_comprehensive import resource_comprehensive_wf

    _run_and_wait(resource_comprehensive_wf, x=42)


def test_pod_template_example():
    from examples.pod_template_example import wf

    _run_and_wait(wf, name="Hello")


def test_pod_template_comprehensive():
    from examples.pod_template_comprehensive import pod_template_comprehensive_wf

    _run_and_wait(pod_template_comprehensive_wf, name="Hello")


def test_secret_example():
    from examples.secret_example import wf

    _run_and_wait(wf, name="flyte")


def test_secret_comprehensive():
    from examples.secret_comprehensive import secret_comprehensive_wf

    _run_and_wait(secret_comprehensive_wf)


# =============================================================================
# REFERENCES — each deploys the target first; see _deploy_reference_target
# =============================================================================


def test_reference_task_example():
    from examples.reference_task_example import reference_wf

    _deploy_reference_target()
    _run_and_wait(reference_wf, name="flyte")


def test_reference_launch_plan_example():
    from examples.reference_launch_plan_example import reference_lp_wf

    _deploy_reference_target()
    _run_and_wait(reference_lp_wf, name="flyte")


def test_reference_workflow_example():
    from examples.reference_workflow_example import reference_workflow_wf

    _deploy_reference_target()
    _run_and_wait(reference_workflow_wf, name="flyte")


# =============================================================================
# PLUGINS — need cluster operators or external services
# =============================================================================


@pytest.mark.plugins
def test_bigquery():
    from examples.bigquery import no_io_wf

    _run_and_wait(no_io_wf)


@pytest.mark.plugins
@pytest.mark.xfail(
    strict=True,
    reason=(
        "spark_with_pod_templates cannot create its driver pod: the namespace quota requires "
        "limits.cpu on every container and the Spark driver pod comes up without one — "
        "'pods ...-driver is forbidden: failed quota: project-quota: must specify limits.cpu "
        "for: spark-kubernetes-driver'. The shim emits the right config (driver_pod carries a "
        "spark-kubernetes-driver container with limits, and spark_conf sets "
        "spark.kubernetes.driver.limit.cores), so the pod templates are not being honoured "
        "downstream. Task-level limits, spark_conf limits, matching the primary container name "
        "and an explicit container in the pod spec all had no effect on the created pod. "
        "The other three Spark tasks in the same example pass."
    ),
)
def test_spark():
    from examples.plugins.spark_example import my_spark

    _run_and_wait(my_spark)


@pytest.mark.plugins
def test_ray():
    from examples.plugins.ray_example import ray_workflow

    _run_and_wait(ray_workflow)


@pytest.mark.plugins
def test_ray_autoscaling():
    from examples.plugins.ray_example import ray_autoscaling_workflow

    _run_and_wait(ray_autoscaling_workflow)


@pytest.mark.plugins
def test_dask():
    from examples.plugins.dask_example import dask_workflow

    _run_and_wait(dask_workflow, size=1000)


@pytest.mark.plugins
def test_pytorch_training():
    from examples.plugins.pytorch_example import pytorch_training_wf

    _run_and_wait(pytorch_training_wf)


@pytest.mark.plugins
@pytest.mark.skip(
    strict=True,
    reason=(
        "flyteplugins-pytorch regression vs v1. With nnodes>1 the worker pod has no rank 0, "
        "and task.py:373 does `result = out[0] if 0 in out else None` — that None is then "
        "serialized against the task's `-> float` and rejected. v1 raised IgnoreOutputs() so "
        "non-master replicas wrote no outputs at all (flytekitplugins/kfpytorch/task.py:487). "
        "v2 has no IgnoreOutputs equivalent, so the shim cannot bridge it; needs an upstream fix."
    ),
)
def test_pytorch_multinode():
    from examples.plugins.pytorch_example import pytorch_multinode_wf

    _run_and_wait(pytorch_multinode_wf)


@pytest.mark.plugins
def test_pytorch_no_restart():
    from examples.plugins.pytorch_example import pytorch_no_restart_wf

    _run_and_wait(pytorch_no_restart_wf)
