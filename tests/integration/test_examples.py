"""One integration test per example in examples/, run against a real Flyte v2 cluster.

Adding a test is three lines — import the entrypoint and hand it to ``_run``:

    def test_hello():
        from examples.hello import wf

        _run(wf, "name='flyte'")

The import is doing real work: it fails loudly if the file is renamed, the entrypoint is
renamed, or a dependency is missing, and ``_run`` reads the file path and function name off
the imported object, so there is nothing to keep in sync by hand.

Each example still *executes* in its own subprocess (via examples/run_example.py). It cannot
run in-process: the shim registers every ``@workflow`` into one global ``parent_env`` keyed
by function name, and six examples define ``wf``, so importing two of them silently
overwrites the first — the test would pass while running the wrong workflow. Importing here
is only a name check; nothing is deployed or run from this process.

Opt-in only: deselected by default (`addopts = -m 'not integration'`) and skipped without
FLYTE_API_KEY, so the normal `uv run pytest` is unaffected.

    FLYTE_API_KEY=... uv run pytest tests/integration -v -s -m integration
    FLYTE_API_KEY=... uv run pytest tests/integration -v -s -m "integration and not plugins"
    FLYTE_API_KEY=... uv run pytest tests/integration -v -s -m integration -k hello

The `plugins` marker covers examples needing cluster operators (Spark/Ray/Dask/PyTorch) or
external services (BigQuery). The secret examples need an `API_TOKEN` secret in the target
project: `uv run flyte create secret API_TOKEN <value>`.
"""

import inspect
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).parents[2]
RUNNER = str(ROOT / "examples" / "run_example.py")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.getenv("FLYTE_API_KEY"), reason="FLYTE_API_KEY not set"),
]


def _example(obj: Any) -> str:
    """Path of the example file defining *obj*, relative to the repo root."""
    target = getattr(obj, "func", obj)
    path = Path(inspect.getfile(target) if not isinstance(obj, ModuleType) else obj.__file__)
    return str(path.relative_to(ROOT))


def _invoke(*argv: str, expect_failed: bool = False) -> None:
    env = {**os.environ}
    if expect_failed:
        env["EXPECT_FAILED"] = "1"
    subprocess.run([sys.executable, RUNNER, *argv], cwd=ROOT, check=True, env=env)


def _run(entrypoint: Any, *args: str, expect_failed: bool = False) -> None:
    """Run a shimmed task/workflow on the cluster.

    *args* are ``key=expression`` strings evaluated in the example's own namespace, so
    module-local names work (e.g. ``priority=Priority.MEDIUM``).
    """
    _invoke(_example(entrypoint), entrypoint.func.__name__, *args, expect_failed=expect_failed)


def _deploy(module: ModuleType, expression: str) -> None:
    """Deploy something from *module*, e.g. ``lp`` or ``greet_wf.parent_env()``."""
    _invoke("--deploy", _example(module), expression)


def _deploy_reference_target() -> None:
    """Register the tasks and launch plans the reference_* examples resolve against.

    They cannot rely on test_deploy_reference_task_target having run: under ``-n`` it may
    land on another worker or run later. Registration is idempotent.
    """
    from examples import reference_task_target

    _deploy(reference_task_target, "greet_wf.parent_env()")


# =============================================================================
# DEPLOYS
# =============================================================================


def test_deploy_reference_task_target():
    _deploy_reference_target()


def test_deploy_launchplan():
    from examples import launchplan

    _deploy(launchplan, "lp")


def test_deploy_launchplan_comprehensive():
    from examples import launchplan_comprehensive

    _deploy(launchplan_comprehensive, "alias_lp")


# =============================================================================
# BASICS
# =============================================================================


def test_hello():
    from examples.hello import wf

    _run(wf, "name='flyte'")


def test_conditional_wf():
    from examples.conditional_wf import conditional_wf

    _run(conditional_wf, "x=10")


def test_control_flow_comprehensive():
    from examples.control_flow_comprehensive import control_flow_wf

    _run(control_flow_wf, "data=[1,2,3,4,5]", "factor=10", "n_dynamic=4")


def test_datatypes_comprehensive():
    from examples.datatypes_comprehensive import datatypes_wf

    _run(
        datatypes_wf,
        "values=[1,2,3,4,5]",
        "name='Alice'",
        "age=30",
        "score=85.5",
        "dt=datetime(2025, 1, 15, 10, 30, 0)",
        "duration=timedelta(hours=2, minutes=30)",
        "priority=Priority.MEDIUM",
    )


def test_deck_example():
    from examples.deck_example import wf

    _run(wf, "name='flyte'")


def test_subworkflow_dynamic():
    from examples.subworkflow_dynamic import wf

    _run(wf, "n=3", "name='test'")


def test_task_params_comprehensive():
    from examples.task_params_comprehensive import all_task_params_wf

    _run(all_task_params_wf, "x=5")


# =============================================================================
# EDGE CASES
# =============================================================================


def test_edge_cases_many_tasks():
    from examples.edge_cases import many_tasks_wf

    _run(many_tasks_wf, "x=0")


def test_edge_cases_single_task():
    from examples.edge_cases import single_task_wf

    _run(single_task_wf, "x=5")


def test_edge_cases_side_effect():
    from examples.edge_cases import side_effect_wf

    _run(side_effect_wf)


def test_edge_cases_long_timeout():
    from examples.edge_cases import long_timeout_wf

    _run(long_timeout_wf, "x=42")


def test_edge_cases_error():
    """This one raises on purpose — the run is expected to end FAILED."""
    from examples.edge_cases import error_wf

    _run(error_wf, "x=99", expect_failed=True)


# =============================================================================
# IMAGES
# =============================================================================


def test_image():
    from examples.image import my_task

    _run(my_task)


def test_image_comprehensive():
    from examples.image_comprehensive import image_comprehensive_wf

    _run(image_comprehensive_wf)


# =============================================================================
# MAP TASKS
# =============================================================================


def test_map_task():
    from examples.map_task import map_workflow

    _run(map_workflow)


def test_map_task_advanced():
    from examples.map_task_advanced import map_task_advanced_wf

    _run(map_task_advanced_wf, "data=[1,2,3,4,5]")


# =============================================================================
# RESOURCES, POD TEMPLATES, SECRETS
# =============================================================================


def test_resource_comprehensive():
    from examples.resource_comprehensive import resource_comprehensive_wf

    _run(resource_comprehensive_wf, "x=42")


def test_pod_template_example():
    from examples.pod_template_example import wf

    _run(wf, "name='Hello'")


def test_pod_template_comprehensive():
    from examples.pod_template_comprehensive import pod_template_comprehensive_wf

    _run(pod_template_comprehensive_wf, "name='Hello'")


def test_secret_example():
    from examples.secret_example import wf

    _run(wf, "name='flyte'")


def test_secret_comprehensive():
    from examples.secret_comprehensive import secret_comprehensive_wf

    _run(secret_comprehensive_wf)


# =============================================================================
# REFERENCES — each deploys the target first; see _deploy_reference_target
# =============================================================================


def test_reference_task_example():
    from examples.reference_task_example import reference_wf

    _deploy_reference_target()
    _run(reference_wf, "name='flyte'")


def test_reference_launch_plan_example():
    from examples.reference_launch_plan_example import reference_lp_wf

    _deploy_reference_target()
    _run(reference_lp_wf, "name='flyte'")


def test_reference_workflow_example():
    from examples.reference_workflow_example import reference_workflow_wf

    _deploy_reference_target()
    _run(reference_workflow_wf, "name='flyte'")


# =============================================================================
# PLUGINS — need cluster operators or external services
# =============================================================================


@pytest.mark.plugins
def test_bigquery():
    from examples.bigquery import no_io_wf

    _run(no_io_wf)


@pytest.mark.plugins
def test_spark():
    from examples.plugins.spark_example import my_spark

    _run(my_spark)


@pytest.mark.plugins
def test_ray():
    from examples.plugins.ray_example import ray_workflow

    _run(ray_workflow)


@pytest.mark.plugins
def test_ray_autoscaling():
    from examples.plugins.ray_example import ray_autoscaling_workflow

    _run(ray_autoscaling_workflow)


@pytest.mark.plugins
def test_dask():
    from examples.plugins.dask_example import dask_workflow

    _run(dask_workflow, "size=1000")


@pytest.mark.plugins
def test_pytorch_training():
    from examples.plugins.pytorch_example import pytorch_training_wf

    _run(pytorch_training_wf)


@pytest.mark.plugins
def test_pytorch_multinode():
    from examples.plugins.pytorch_example import pytorch_multinode_wf

    _run(pytorch_multinode_wf)


@pytest.mark.plugins
def test_pytorch_no_restart():
    from examples.plugins.pytorch_example import pytorch_no_restart_wf

    _run(pytorch_no_restart_wf)
