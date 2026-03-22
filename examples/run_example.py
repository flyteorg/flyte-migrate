"""Helper to run any example file with run.wait().

Usage: uv run python examples/run_example.py examples/hello.py wf name=flyte
       uv run python examples/run_example.py examples/map_task.py map_workflow
       uv run python examples/run_example.py examples/plugins/pytorch_example.py pytorch_training_wf
"""

import importlib.util
import logging
import sys

if len(sys.argv) < 3:
    print("Usage: python run_example.py <example_file> <workflow_func_name> [key=value ...]")
    sys.exit(1)

example_file = sys.argv[1]
wf_name = sys.argv[2]
kwargs = {}
for arg in sys.argv[3:]:
    k, v = arg.split("=", 1)
    # Try to parse as Python literal
    try:
        v = eval(v)
    except Exception:
        pass
    kwargs[k] = v

# Load the example module from file path
spec = importlib.util.spec_from_file_location("example_mod", example_file)
mod = importlib.util.module_from_spec(spec)
sys.modules["example_mod"] = mod
spec.loader.exec_module(mod)

# Get the workflow function
wf_func = getattr(mod, wf_name)

import flyte

flyte.init_from_config(log_level=logging.DEBUG)
run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(wf_func, **kwargs)
print("Run name:", run.name)
print("Run URL:", run.url)
run.wait(quiet=False)
print("DONE")
