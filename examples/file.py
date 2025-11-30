import flyte_migrate  # noqa: F401, I001

import flytekit as fl
import pandas as pd
import os
from dataclasses import dataclass
import tempfile

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
def upload_data() -> FlyteTypes:
    file_path = tempfile.NamedTemporaryFile(delete=False)
    file_path.write(b"Hello, World!")

    fs = FlyteTypes(
        file=fl.FlyteFile(file_path.name),
    )
    return fs

@fl.task(container_image=image)
def download_data(res: FlyteTypes):
    f = open(res.file, "r")
    assert f.read() == "Hello, World!"

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
            df = df[df['John'].isna() == False]
            df.to_csv(w, index=False)
    return new_file

@fl.workflow()
def wf():
    o1 = load_csv()
    o2 = remove_some_rows(ff=o1)
    download_file(ff=o2)
    o3 = upload_data()
    download_data(res=o3)
