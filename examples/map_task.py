import functools

from flytekit import map_task, task, workflow


@task
def multi_input_task(quantity: int, price: float, shipping: float) -> float:
    return quantity * price * shipping


@workflow
def map_workflow(list_q: list[int] = [10, 13, 12, 100, 11, 12, 10], p: float = 6.0, s: float = 7.0) -> list[float]:
    partial_task = functools.partial(multi_input_task, price=p, shipping=s)
    return map_task(partial_task)(list_q)
