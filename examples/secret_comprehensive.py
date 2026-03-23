import flyte_migrate  # noqa: F401, I001
import logging
import os
from pathlib import Path
from typing import Tuple

from flytekit import Secret, task, workflow


# --- Task 1: Mixed mounts (ENV_VAR + FILE) ---
@task(
    secret_requests=[
        Secret(group="", key="API_TOKEN", env_var="API_TOKEN_ENV"),
        Secret(group="", key="API_TOKEN", mount_requirement=Secret.MountType.FILE),
    ]
)
def mixed_mount_task() -> Tuple[str, str]:
    """Access the same secret via both ENV_VAR and FILE mount."""
    env_val = os.getenv("API_TOKEN_ENV", "NOT_SET")

    file_path = Path("/etc/flyte/secrets/API_TOKEN")
    try:
        file_val = file_path.read_text().strip()
    except FileNotFoundError:
        file_val = "FILE_NOT_FOUND"

    print(f"ENV: {env_val}, FILE: {file_val}")
    return env_val, file_val


# --- Task 2: Secret with empty group ---
@task(
    secret_requests=[
        Secret(group="", key="API_TOKEN", env_var="API_TOKEN_EMPTY_GROUP"),
    ]
)
def empty_group_secret_task() -> str:
    """Access a secret that has group='' (empty string)."""
    val = os.getenv("API_TOKEN_EMPTY_GROUP", "NOT_SET")
    print(f"Empty group secret: {val}")
    return val


# --- Task 3: Multiple ENV_VAR secrets ---
@task(
    secret_requests=[
        Secret(group="", key="API_TOKEN", env_var="TOKEN_A"),
        Secret(group="", key="API_TOKEN", env_var="TOKEN_B"),
    ]
)
def multi_env_secret_task() -> Tuple[str, str]:
    """Access the same secret key mapped to different env vars."""
    a = os.getenv("TOKEN_A", "NOT_SET")
    b = os.getenv("TOKEN_B", "NOT_SET")
    print(f"TOKEN_A={a}, TOKEN_B={b}")
    return a, b


# --- Workflow combining all secret tasks ---
@workflow
def secret_comprehensive_wf() -> Tuple[Tuple[str, str], str, Tuple[str, str]]:
    mixed = mixed_mount_task()
    empty = empty_group_secret_task()
    multi = multi_env_secret_task()
    return mixed, empty, multi


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(secret_comprehensive_wf)
    print(run.name)
    print(run.url)
