"""v1 FlyteDirectory crossing task boundaries — uploaded on the way out, downloaded on the way in."""

import flyte_migrate  # noqa: F401, I001
import logging
import os
from pathlib import Path

from flytekit import task, workflow
from flytekit.types.directory import FlyteDirectory


@task
def make_dir(n: int) -> FlyteDirectory:
    out = Path("/tmp/reports")
    out.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (out / f"report_{i}.txt").write_text(f"report {i}")
    return FlyteDirectory(path=str(out))


@task
def count_files(d: FlyteDirectory) -> int:
    root = Path(os.fspath(d))
    files = sorted(p.name for p in root.iterdir())
    print(f"got {files}")
    return len(files)


@workflow
def wf(n: int) -> int:
    return count_files(d=make_dir(n=n))


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(wf, n=3)
    print(run.name)
    print(run.url)
    run.wait(quiet=False)
