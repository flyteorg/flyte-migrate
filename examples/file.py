import flyte_migrate  # noqa: F401, I001

import flytekit as fl
import pandas as pd
import os


image = fl.ImageSpec(packages=["pandas"])


@fl.task(container_image=image)
def download_file(ff: fl.FlyteFile):
    print(os.path.isfile(ff.path)) #TODO this should be False
    ff.download()
    print(os.path.isfile(ff.path))


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
    f = load_csv()
    f2 = remove_some_rows(f)
    download_file(f2)
