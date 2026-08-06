"""Runs every example in examples/ against a real Flyte v2 cluster.

Opt-in only: deselected by default (`addopts = -m 'not integration'`) and skipped without
FLYTE_API_KEY, so the normal `uv run pytest` is unaffected.

    FLYTE_API_KEY=... uv run pytest tests/integration -v -s -m integration
    FLYTE_API_KEY=... uv run pytest tests/integration -v -s -m "integration and not plugins"

Each example runs in its own subprocess (via examples/run_example.py) — examples define
TaskEnvironments with overlapping names, so loading several into one process collides.

The `plugins` marker covers examples needing cluster operators (Spark/Ray/Dask/PyTorch) or
external services (BigQuery). The secret examples need an `API_TOKEN` secret in the target
project: `uv run flyte create secret API_TOKEN <value>`.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
RUNNER = str(ROOT / "examples" / "run_example.py")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.getenv("FLYTE_API_KEY"), reason="FLYTE_API_KEY not set"),
]

# (example file, expression for the deployable). These run before the run-tests below,
# because the reference_* examples resolve tasks/launch plans registered here.
DEPLOY = [
    ("reference_task_target.py", "greet_wf.parent_env()"),
    ("launchplan.py", "lp"),
    ("launchplan_comprehensive.py", "alias_lp"),
]

# (example file, entrypoint, args as `key=expr` evaluated in the example's namespace)
RUN = [
    ("hello.py", "wf", ["name='flyte'"]),
    ("conditional_wf.py", "conditional_wf", ["x=10"]),
    ("control_flow_comprehensive.py", "control_flow_wf", ["data=[1,2,3,4,5]", "factor=10", "n_dynamic=4"]),
    (
        "datatypes_comprehensive.py",
        "datatypes_wf",
        [
            "values=[1,2,3,4,5]",
            "name='Alice'",
            "age=30",
            "score=85.5",
            "dt=datetime(2025, 1, 15, 10, 30, 0)",
            "duration=timedelta(hours=2, minutes=30)",
            "priority=Priority.MEDIUM",
        ],
    ),
    ("deck_example.py", "wf", ["name='flyte'"]),
    ("edge_cases.py", "many_tasks_wf", ["x=0"]),
    ("edge_cases.py", "single_task_wf", ["x=5"]),
    ("edge_cases.py", "side_effect_wf", []),
    ("edge_cases.py", "long_timeout_wf", ["x=42"]),
    ("edge_cases.py", "error_wf", ["x=99"]),
    ("image.py", "my_task", []),
    ("image_comprehensive.py", "image_comprehensive_wf", []),
    ("map_task.py", "map_workflow", []),
    ("map_task_advanced.py", "map_task_advanced_wf", ["data=[1,2,3,4,5]"]),
    ("pod_template_example.py", "wf", ["name='Hello'"]),
    ("pod_template_comprehensive.py", "pod_template_comprehensive_wf", ["name='Hello'"]),
    ("resource_comprehensive.py", "resource_comprehensive_wf", ["x=42"]),
    ("secret_example.py", "wf", ["name='flyte'"]),
    ("secret_comprehensive.py", "secret_comprehensive_wf", []),
    ("subworkflow_dynamic.py", "wf", ["n=3", "name='test'"]),
    ("task_params_comprehensive.py", "all_task_params_wf", ["x=5"]),
    ("reference_task_example.py", "reference_wf", ["name='flyte'"]),
    ("reference_launch_plan_example.py", "reference_lp_wf", ["name='flyte'"]),
    ("reference_workflow_example.py", "reference_workflow_wf", ["name='flyte'"]),
    pytest.param("bigquery.py", "no_io_wf", [], marks=pytest.mark.plugins),
    pytest.param("plugins/spark_example.py", "my_spark", [], marks=pytest.mark.plugins),
    pytest.param("plugins/ray_example.py", "ray_workflow", [], marks=pytest.mark.plugins),
    pytest.param("plugins/ray_example.py", "ray_autoscaling_workflow", [], marks=pytest.mark.plugins),
    pytest.param("plugins/dask_example.py", "dask_workflow", ["size=1000"], marks=pytest.mark.plugins),
    pytest.param("plugins/pytorch_example.py", "pytorch_training_wf", [], marks=pytest.mark.plugins),
    pytest.param("plugins/pytorch_example.py", "pytorch_multinode_wf", [], marks=pytest.mark.plugins),
    pytest.param("plugins/pytorch_example.py", "pytorch_no_restart_wf", [], marks=pytest.mark.plugins),
]

# The only example that is supposed to end up FAILED — it raises on purpose.
EXPECT_FAILED = {"edge_cases.py:error_wf"}


def _run(*argv, **env):
    subprocess.run(
        [sys.executable, RUNNER, *argv],
        cwd=ROOT,
        check=True,
        env={**os.environ, **env},
    )


@pytest.mark.parametrize("rel,expr", DEPLOY, ids=[d[0] for d in DEPLOY])
def test_deploy_example(rel, expr):
    _run("--deploy", f"examples/{rel}", expr)


@pytest.mark.parametrize("rel,entrypoint,args", RUN)
def test_run_example(rel, entrypoint, args):
    env = {"EXPECT_FAILED": "1"} if f"{rel}:{entrypoint}" in EXPECT_FAILED else {}
    _run(f"examples/{rel}", entrypoint, *args, **env)
