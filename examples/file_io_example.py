import flyte_migrate  # noqa: F401, I001
import logging
import os
import tempfile

from flytekit import task, workflow
from flytekit.types.file import FlyteFile
from flytekit.types.directory import FlyteDirectory


@task
def write_csv(data: str) -> FlyteFile:
    """Write data to a CSV file and return a FlyteFile reference."""
    working_dir = tempfile.mkdtemp()
    filepath = os.path.join(working_dir, "output.csv")
    with open(filepath, "w") as f:
        f.write("name,value\n")
        f.write(data)
    return FlyteFile(filepath)


@task
def read_csv(ff: FlyteFile) -> str:
    """Read a FlyteFile and return its contents."""
    with open(ff, "r") as f:
        return f.read()


@task
def write_directory(items: list[str]) -> FlyteDirectory:
    """Write multiple files into a directory and return a FlyteDirectory reference."""
    working_dir = tempfile.mkdtemp()
    for i, item in enumerate(items):
        filepath = os.path.join(working_dir, f"file_{i}.txt")
        with open(filepath, "w") as f:
            f.write(item)
    return FlyteDirectory(working_dir)


@task
def count_files_in_dir(fd: FlyteDirectory) -> int:
    """Count the number of files in a FlyteDirectory."""
    return len(os.listdir(fd))


@workflow
def file_io_wf(data: str = "alice,100\nbob,200\n") -> str:
    """Demonstrates passing files between tasks using FlyteFile and FlyteDirectory."""
    ff = write_csv(data=data)
    contents = read_csv(ff=ff)
    return contents


@workflow
def directory_wf(items: list[str] = ["hello", "world", "flyte"]) -> int:
    """Demonstrates passing directories between tasks using FlyteDirectory."""
    fd = write_directory(items=items)
    count = count_files_in_dir(fd=fd)
    return count


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(file_io_wf)
    print(run.name)
    print(run.url)
