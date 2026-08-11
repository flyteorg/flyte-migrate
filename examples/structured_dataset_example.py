"""v1 StructuredDataset crossing task boundaries via the v2 DataFrame transformer.

The producer wraps a pandas DataFrame in a v1 ``StructuredDataset``; the consumer opens
it back into pandas with the v1 ``open(...).all()`` API.  pandas ships in the task image
via ImageSpec, which the shim mirrors onto the parent workflow environment so the driver
can (de)serialize the dataframe too.
"""

import flyte_migrate  # noqa: F401, I001
import logging

from flytekit import ImageSpec, StructuredDataset, task, workflow

image = ImageSpec(packages=["pandas", "pyarrow"])


@task(container_image=image)
def make_dataset(rows: int) -> StructuredDataset:
    import pandas as pd

    df = pd.DataFrame({"i": list(range(rows)), "squared": [i * i for i in range(rows)]})
    return StructuredDataset(dataframe=df)


@task(container_image=image)
def sum_squares(sd: StructuredDataset) -> int:
    import pandas as pd

    df = sd.open(pd.DataFrame).all()
    return int(df["squared"].sum())


@workflow
def wf(rows: int) -> int:
    return sum_squares(sd=make_dataset(rows=rows))


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(wf, rows=5)
    print(run.name)
    print(run.url)
    run.wait(quiet=False)
