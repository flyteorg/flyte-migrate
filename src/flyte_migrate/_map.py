from typing import Any, Optional, Union

import flyte
import flytekit.remote


class MapShim:
    """Shim that wraps ``flyte.map()`` to provide a v1-compatible ``map_task`` interface.

    In FlyteKit v1, ``map_task`` accepted concurrency, min_successes, and
    min_success_ratio parameters.  This shim forwards ``concurrency`` to
    ``flyte.map()`` (which supports it natively) and accepts ``min_successes``
    and ``min_success_ratio`` for API compatibility without forwarding them
    (v2 does not support these parameters).
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
        # concurrency is forwarded to flyte.map() which supports it as ``concurrency: int = 0``.
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

        The ``concurrency`` parameter is forwarded to ``flyte.map()`` when set.
        """
        map_kwargs: dict[str, Any] = {}
        if self.concurrency is not None:
            map_kwargs["concurrency"] = self.concurrency

        if args:
            return list(flyte.map(self.target, *args, **map_kwargs))
        return list(flyte.map(self.target, *kwargs.values(), **map_kwargs))


flytekit.map_task = MapShim
