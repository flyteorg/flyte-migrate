from typing import Optional, Union

import flyte
import flytekit.remote


class MapShim:
    def __init__(
        self,
        target: Union[
            flytekit.LaunchPlan,
            flytekit.PythonFunctionTask,
            flytekit.remote.FlyteLaunchPlan,
        ],
        concurrency: Optional[int] = None,
        min_successes: Optional[int] = None,
        min_success_ratio: Optional[float] = None,
        **kwargs,
    ):
        self.target = target
        self.concurrency = concurrency
        self.min_successes = min_successes
        self.min_success_ratio = min_success_ratio
        self.kwargs = kwargs

    def __call__(self, *args, **kwargs):
        if args:
            return list(flyte.map(self.target, *args))
        return list(flyte.map(self.target, *kwargs.values()))


flytekit.map_task = MapShim
