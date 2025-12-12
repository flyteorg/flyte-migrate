import logging
import os
import typing
from dataclasses import dataclass
from pathlib import Path

import flytekit as fl
import pandas as pd

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
    my_csv = fl.FlyteFile.from_source(uri)
    return my_csv


@fl.task(container_image=image)
def remove_some_rows(ff: fl.FlyteFile) -> fl.FlyteFile:
    new_file = fl.FlyteFile.new_remote_file("data_without_nan.csv")
    with ff.open("r") as r:
        with new_file.open("w") as w:
            df = pd.read_csv(r)
            df = df[~df["John"].isna()]
            df.to_csv(w, index=False)
    return new_file


@fl.workflow()
def wf():
    o1 = load_csv()
    o2 = remove_some_rows(ff=o1)
    download_file(ff=o2)
    o3 = upload_data(remote_path=None)
    download_flyte_types(res=o3)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(wf)
    print(run.name)
    print(run.url)
