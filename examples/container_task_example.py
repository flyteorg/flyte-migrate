"""v1 raw ContainerTask on v2: no flytekit inside the container, inputs templated into the
command, outputs read back from files in the output directory."""

import flyte_migrate  # noqa: F401, I001
import logging

from flytekit import ContainerTask, kwtypes, workflow

calculate_ellipse_area = ContainerTask(
    name="ellipse-area",
    image="python:3.12-slim",
    input_data_dir="/var/inputs",
    output_data_dir="/var/outputs",
    inputs=kwtypes(a=float, b=float),
    outputs=kwtypes(area=float),
    command=[
        "python",
        "-c",
        "import math; open('/var/outputs/area', 'w').write(str(math.pi * {{.inputs.a}} * {{.inputs.b}}))",
    ],
)


@workflow
def wf(a: float, b: float) -> float:
    return calculate_ellipse_area(a=a, b=b)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(wf, a=3.0, b=4.0)
    print(run.name)
    print(run.url)
    run.wait(quiet=False)
