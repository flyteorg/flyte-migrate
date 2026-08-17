"""Mixing v1 and v2 code: a v1 workflow whose task image is built with the v2 ``flyte.Image`` API.

flyte-migrate lets you adopt v2 incrementally — keep ``@task``/``@workflow`` from
flytekit while switching individual pieces (here, the image definition) to the v2 SDK.
A ``flyte.Image`` passed as ``container_image`` is used as-is, without modification, so
it must include ``flytekit`` and ``flyte-migrate`` for the container to load this file.
"""

import flyte
from flytekit import task, workflow

image = flyte.Image.from_debian_base().with_pip_packages("flytekit", "flyte-migrate", "pandas", "ty")


@task(container_image=image, cache=True, retries=2)
def summarize(name: str) -> str:
    import pandas as pd

    df = pd.DataFrame({"name": [name]})
    return f"Hello, {df.at[0, 'name']}!"


@workflow
def wf(name: str) -> str:
    return summarize(name=name)
