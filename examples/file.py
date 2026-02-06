import logging
import os
import typing
from dataclasses import dataclass
from pathlib import Path

import flytekit as fl
import pandas as pd
from flytekit.types.file import FileExt

import flyte_migrate  # noqa: F401


@dataclass
class FlyteTypes:
    file: fl.FlyteFile


image = fl.ImageSpec(packages=["pandas"])


@fl.task(container_image=image)
def download_file(ff: fl.FlyteFile):
    local_path = ff.download()
    print(os.path.isfile(local_path))
    df = pd.read_csv(local_path)
    print(df)


@fl.task(container_image=image)
def upload_data(remote_path: typing.Optional[str]) -> FlyteTypes:
    path = str(Path(fl.current_context().working_directory) / "data.csv")
    d = {"col1": [0, 1, 2, 3], "col2": pd.Series([2, 3], index=[2, 3])}
    data = pd.DataFrame(data=d, index=[0, 1, 2, 3])
    data.to_csv(path)
    file = fl.FlyteFile(path=path, remote_path=remote_path)
    fs = FlyteTypes(file=file)
    return fs


@fl.task(container_image=image)
def download_flyte_types(res: FlyteTypes):
    local_path = res.file.download()
    df = pd.read_csv(local_path)
    print(df)
    with open(res.file, "r") as f:
        df = pd.read_csv(f)
        print(df)


@fl.task(container_image=image)
def load_csv(uri: str = "https://people.sc.fsu.edu/~jburkardt/data/csv/addresses.csv") -> fl.FlyteFile:
    my_csv = fl.FlyteFile[typing.Annotated[str, FileExt("csv")]].from_source(uri)
    return my_csv


@fl.task(container_image=image)
def remove_some_rows(ff: fl.FlyteFile) -> fl.FlyteFile:
    new_file = fl.FlyteFile[typing.TypeVar("csv")].new_remote_file("data_without_nan.csv")
    with ff.open("r") as r:
        with new_file.open("w") as w:
            df = pd.read_csv(r)
            df = df[~df["John"].isna()]
            df.to_csv(w, index=False)
    return new_file


@fl.workflow()
def wf():
    uri = "https://people.sc.fsu.edu/~jburkardt/data/csv/addresses.csv"
    o1 = load_csv(uri=uri)
    o2 = remove_some_rows(ff=o1)
    download_file(ff=o2)
    o3 = upload_data(remote_path=None)
    download_flyte_types(res=o3)


@fl.task(container_image=image)
def check_src(f1: fl.FlyteFile, f2: typing.Union[str, fl.FlyteFile]) -> bool:
    expected_uri = f2 if isinstance(f2, str) else str(f2)
    return str(f1) == expected_uri


@fl.workflow()
def check_file_property_wf():
    """
    File one is same with file 2 from s3 or external uri?
    1. Local
    res1 is True where o1 and uri are from people.sc.fsu.edu.
    res2 is False where o1 and o2 are from different local path
    2. Online
    res1 is False because o1 is from s3 uri instead of people.sc.fsu.edu.
    res2 is False where o1 and o2 are from different s3 uri path.
    """
    uri = "https://people.sc.fsu.edu/~jburkardt/data/csv/addresses.csv"
    o1 = load_csv(uri=uri)
    res1 = check_src(o1, uri)
    print(res1)
    o2 = remove_some_rows(ff=o1)
    res2 = check_src(o1, str(o2))
    print(res2)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    context = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG)
    run = context.run(wf)
    print(run.name)
    print(run.url)
    run = context.run(check_file_property_wf)
    print(run.name)
    print(run.url)
