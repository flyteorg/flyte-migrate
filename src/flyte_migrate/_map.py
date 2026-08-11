import math
from typing import Any, Optional, Union

import flyte
import flytekit.remote


class MapShim:
    """Shim that wraps ``flyte.map()`` to provide a v1-compatible ``map_task`` interface.

    ``concurrency`` is forwarded to ``flyte.map()``, which supports it natively.
    ``min_successes`` / ``min_success_ratio`` are enforced client-side: ``flyte.map()``
    returns failed sub-tasks as ``Exception`` objects (``return_exceptions=True``), so
    the shim counts successes, raises when the threshold is not met (v1 default:
    every sub-task must succeed), and otherwise substitutes ``None`` for failures —
    matching v1's ``List[Optional[T]]`` output when a ratio is set.
    ``run_all_sub_nodes`` is inherently satisfied — v2 always runs every sub-task and
    collects failures rather than aborting early.
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
        min_success_ratio: float = 1.0,
        run_all_sub_nodes: bool = False,
        **kwargs: Any,
    ) -> None:
        self.target = target
        self.concurrency = concurrency
        self.min_successes = min_successes
        self.min_success_ratio = min_success_ratio
        self.kwargs = kwargs

    def __call__(self, *args: Any, **kwargs: Any) -> list:
        """Execute the mapped task over the provided inputs.

        Positional arguments are passed directly to ``flyte.map()``.  When only
        keyword arguments are supplied, their values are unpacked as positional
        arguments (matching v1 ``map_task`` calling convention).
        """
        map_kwargs: dict[str, Any] = {}
        if self.concurrency is not None:
            map_kwargs["concurrency"] = self.concurrency

        if args:
            results = list(flyte.map(self.target, *args, **map_kwargs))
        else:
            results = list(flyte.map(self.target, *kwargs.values(), **map_kwargs))

        failures = [r for r in results if isinstance(r, BaseException)]
        if not failures:
            return results

        min_successes = self.min_successes
        if min_successes is None:
            ratio = 1.0 if self.min_success_ratio is None else self.min_success_ratio
            min_successes = math.ceil(ratio * len(results))
        if len(results) - len(failures) < min_successes:
            raise failures[0]
        return [None if isinstance(r, BaseException) else r for r in results]


flytekit.map_task = MapShim
