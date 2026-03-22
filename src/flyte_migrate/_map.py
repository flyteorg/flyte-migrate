from typing import Any, Optional, Union

import flyte
import flytekit.remote


class MapShim:
    """Shim that wraps ``flyte.map()`` to provide a v1-compatible ``map_task`` interface.

    In FlyteKit v1, ``map_task`` accepted concurrency, min_successes, and
    min_success_ratio parameters.  This shim accepts those parameters for
    API compatibility but delegates to ``flyte.map()`` which does not yet
    support them.
    """

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
        **kwargs: Any,
    ) -> None:
        self.target = target
        # TODO: concurrency is accepted for v1 API compat but not forwarded to flyte.map() yet.
        self.concurrency = concurrency
        # TODO: min_successes is accepted for v1 API compat but not forwarded to flyte.map() yet.
        self.min_successes = min_successes
        # TODO: min_success_ratio is accepted for v1 API compat but not forwarded to flyte.map() yet.
        self.min_success_ratio = min_success_ratio
        self.kwargs = kwargs

    def __call__(self, *args: Any, **kwargs: Any) -> list:
        """Execute the mapped task over the provided inputs.

        Positional arguments are passed directly to ``flyte.map()``.  When only
        keyword arguments are supplied, their values are unpacked as positional
        arguments (matching v1 ``map_task`` calling convention).
        """
        if args:
            return list(flyte.map(self.target, *args))
        return list(flyte.map(self.target, *kwargs.values()))


flytekit.map_task = MapShim
