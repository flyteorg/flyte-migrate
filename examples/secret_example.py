import flyte_migrate  # noqa: F401, I001
import logging
import os
from pathlib import Path
from typing import Tuple

from flytekit import Secret, task, workflow


@task(secret_requests=[Secret(group="", key="API_TOKEN", env_var="API_TOKEN_ENV")])
def use_secret_env() -> str:
    """
    Access a secret via environment variable.

    Uses Secret with env_var parameter to inject the secret
    as an environment variable into the task container.
    """
    val = os.getenv("API_TOKEN_ENV")
    return f"ENV secret present: {val is not None}"


@task(
    secret_requests=[
        Secret(
            group="",
            key="API_TOKEN",
            mount_requirement=Secret.MountType.FILE,
        )
    ]
)
def use_secret_file() -> str:
    """
    Access a secret via file mount.

    Uses Secret with mount_requirement=FILE to mount the secret
    as a file in the task container at /etc/flyte/secrets/.
    """
    path = Path("/etc/flyte/secrets")
    if os.path.isdir(path):
        with open(f"{path}/API_TOKEN") as f:
            val = f.read().strip()
        return f"FILE secret length: {len(val)}"
    return "FILE secret: not mounted"


@workflow
def secret_wf() -> Tuple[str, str]:
    """
    Demonstrates secret handling in Flyte workflows.

    Exercises: Secret env vars, Secret file mounts, Secret.MountType.
    """
    return (use_secret_env(), use_secret_file())


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(secret_wf)
    print(run.name)
    print(run.url)
