from pathlib import Path

import flytekit
from flyte import Image, Resources, TaskEnvironment


env = TaskEnvironment(
    name="flytekit_workflow",
    resources=Resources(cpu=0.8, memory="800Mi"),
    image=Image.from_debian_base()
    .with_apt_packages("git")
    .with_pip_packages("flytekit", "pandas")
    .with_source_folder(Path(__file__).parent.parent.parent, "./flyte-migrate")
    .with_env_vars({"PYTHONPATH": "./flyte-migrate/src:${PYTHONPATH}"})
)

# TODO: Build subtask's image

flytekit.workflow = env.task
