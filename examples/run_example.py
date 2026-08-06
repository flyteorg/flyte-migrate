"""Helper to run (or deploy) any example file and exit non-zero if it doesn't succeed.

Usage: uv run python examples/run_example.py examples/hello.py wf name=flyte
       uv run python examples/run_example.py examples/map_task.py map_workflow
       uv run python examples/run_example.py --deploy examples/launchplan.py lp

Values are eval'd in the example module's namespace, so module-local names work
(e.g. `priority=Priority.MEDIUM`). Set EXPECT_FAILED=1 to assert the run FAILS.
Auth: FLYTE_API_KEY if set, else .flyte/config.yaml.
"""

import importlib.util
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

args = sys.argv[1:]
deploy = bool(args) and args[0] == "--deploy"
if deploy:
    args = args[1:]
if len(args) < 2:
    print(__doc__)
    sys.exit(1)

example_file, entrypoint, *rest = args

# Load the example module from file path
spec = importlib.util.spec_from_file_location("example_mod", example_file)
mod = importlib.util.module_from_spec(spec)
sys.modules["example_mod"] = mod
spec.loader.exec_module(mod)

kwargs = {}
for arg in rest:
    k, v = arg.split("=", 1)
    # Try to parse as a Python expression in the example's namespace
    try:
        v = eval(v, vars(mod))
    except Exception:
        pass
    kwargs[k] = v

import flyte
from flyte.models import ActionPhase

if os.getenv("FLYTE_API_KEY"):
    flyte.init_from_api_key(
        project=os.getenv("FLYTE_PROJECT", "flyte-migrate"),
        domain=os.getenv("FLYTE_DOMAIN", "development"),
        image_builder="remote",
        root_dir=ROOT,
    )
else:
    flyte.init_from_config(root_dir=ROOT, log_level=logging.DEBUG)

if deploy:
    # entrypoint is an expression on the module, e.g. "lp" or "greet_wf.parent_env()"
    print(flyte.deploy(eval(entrypoint, vars(mod)))[0].summary_repr())
    sys.exit(0)

run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(getattr(mod, entrypoint), **kwargs)
print("Run name:", run.name)
print("Run URL:", run.url)
# The watch stream behind wait() is long-lived and the server drops it periodically
# (grpc UNAVAILABLE "Socket closed"), which says nothing about the run. Re-attach.
for attempt in range(3):
    try:
        run.wait(quiet=False)
        break
    except Exception as e:
        if attempt == 2:
            raise
        print(f"wait() dropped ({type(e).__name__}: {e}); re-attaching")

expected = ActionPhase.FAILED if os.getenv("EXPECT_FAILED") else ActionPhase.SUCCEEDED
print(f"DONE: {run.phase}")
sys.exit(0 if run.phase == expected else 1)
