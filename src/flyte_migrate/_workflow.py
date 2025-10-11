from pathlib import Path

import flytekit
from flyte import Image, Resources, TaskEnvironment

parent_env = TaskEnvironment(
    name="flytekit_workflow",
    resources=Resources(cpu=0.8, memory="800Mi"),
    image=Image.from_debian_base()
    .with_pip_packages("setuptools")
    .with_source_folder(Path(__file__).parent.parent.parent, "./flyte-migrate")
    .with_env_vars({"PYTHONPATH": "./flyte-migrate/src:${PYTHONPATH}"}),
)

flytekit.workflow = parent_env.task
