import logging
import os
from pathlib import Path
from typing import Tuple

from flytekit import Secret, task, workflow


@task(secret_requests=[Secret(group="", key="API_TOKEN", env_var="API_TOKEN_ENV")])
def use_secret_env() -> str:
    val = os.getenv("API_TOKEN_ENV")
    try:
        print("FILE being created ?", os.listdir(Path("/etc/flyte/secrets")))
    except FileNotFoundError:
        print("Didn't mount a File")
    return f"ENV secret: {val}"


@task(secret_requests=[Secret(group="", key="API_TOKEN", mount_requirement=Secret.MountType.FILE)])
def use_secret_file() -> str:
    path = Path("/etc/flyte/secrets")
    if os.path.isdir(path):
        print("FILE being created ?", os.listdir(path))
    with open(f"{path}/API_TOKEN") as f:
        val = f.read().strip()
    return f"FILE secret: {val}"


@workflow
def wf(name: str) -> Tuple[str, str]:
    return (use_secret_env(), use_secret_file())


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(wf, name="flyte")
    print(run.name)
    print(run.url)
