import flyte_migrate  # noqa: F401, I001
import functools
import logging

from flytekit import map_task, task, workflow


@task
def multi_input_task(quantity: int, price: float, shipping: float) -> float:
    return quantity * price * shipping


@workflow
def map_workflow(list_q: list[int] = [10, 13, 12, 100, 11, 12, 10], p: float = 6.0, s: float = 7.0) -> list[float]:
    partial_task = functools.partial(multi_input_task, price=p, shipping=s)
    return map_task(partial_task)(list_q)


if __name__ == "__main__":
    import flyte

    flyte.init_from_config(log_level=logging.DEBUG)
    run = flyte.with_runcontext(mode="remote", log_level=logging.DEBUG).run(map_workflow)
    print(run.name)
    print(run.url)
