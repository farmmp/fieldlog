"""Pipeline integration for Backpressure."""

from __future__ import annotations

from typing import Callable, Optional

from fieldlog.backpressure import Backpressure
from fieldlog.pipeline import Pipeline


class BackpressureStage:
    """A pipeline stage that wraps the next sink with :class:`Backpressure`.

    Parameters
    ----------
    max_pending:
        Queue depth before policy is applied.
    policy:
        ``"drop"`` or ``"block"``.
    timeout:
        Optional timeout in seconds when ``policy="block"``.
    """

    def __init__(
        self,
        *,
        max_pending: int = 100,
        policy: str = "drop",
        timeout: Optional[float] = None,
    ) -> None:
        self._max_pending = max_pending
        self._policy = policy
        self._timeout = timeout
        self._bp: Optional[Backpressure] = None

    def bind(self, sink: Callable) -> Callable:
        """Bind this stage to a downstream *sink* and return the wrapped callable."""
        self._bp = Backpressure(
            sink,
            max_pending=self._max_pending,
            policy=self._policy,
            timeout=self._timeout,
        )
        return self._bp

    def __call__(self, entry: dict) -> None:
        if self._bp is None:
            raise RuntimeError("BackpressureStage has not been bound to a sink")
        self._bp(entry)

    @property
    def dropped_count(self) -> int:
        if self._bp is None:
            return 0
        return self._bp.dropped_count


def backpressure_pipeline(
    *stages,
    max_pending: int = 100,
    policy: str = "drop",
    timeout: Optional[float] = None,
    sink: Callable,
) -> Pipeline:
    """Build a :class:`~fieldlog.pipeline.Pipeline` with a backpressure stage prepended.

    Example
    -------
    >>> bp_stage = BackpressureStage(max_pending=50, policy="drop")
    >>> p = backpressure_pipeline(bp_stage, sink=my_sink)
    >>> p.send(entry)
    """
    bp_stage = BackpressureStage(
        max_pending=max_pending,
        policy=policy,
        timeout=timeout,
    )
    return Pipeline(*stages, bp_stage, sink=sink)
