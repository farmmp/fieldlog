"""Pipeline integration for PriorityQueue."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from fieldlog.priority_queue import PriorityQueue


class PriorityStage:
    """A pipeline stage that buffers entries in a PriorityQueue.

    Entries are *not* forwarded until :meth:`flush` is called, which makes
    this stage suitable for micro-batching or end-of-request flushing.

    Args:
        max_size: Maximum buffer size (0 = unbounded).
    """

    def __init__(self, max_size: int = 0) -> None:
        self._max_size = max_size
        self._queue: Optional[PriorityQueue] = None

    def bind(self, sink: Callable[[Dict[str, Any]], None]) -> "PriorityStage":
        """Attach a downstream sink and return *self* for chaining."""
        self._queue = PriorityQueue(sink, max_size=self._max_size)
        return self

    def __call__(self, entry: Dict[str, Any]) -> None:
        if self._queue is None:
            raise RuntimeError("PriorityStage must be bound to a sink before use")
        self._queue(entry)

    def flush(self) -> int:
        """Flush buffered entries to the downstream sink."""
        if self._queue is None:
            return 0
        return self._queue.flush()

    @property
    def pending(self) -> int:
        """Number of entries waiting to be flushed."""
        return self._queue.pending if self._queue else 0

    @property
    def dropped_count(self) -> int:
        """Entries dropped due to max_size overflow."""
        return self._queue.dropped_count if self._queue else 0


def priority_pipeline(
    *stages,
    max_size: int = 0,
    sink: Callable[[Dict[str, Any]], None],
) -> PriorityStage:
    """Build a PriorityStage wired through optional upstream *stages*.

    The returned :class:`PriorityStage` is the entry-point; call
    ``stage.flush()`` to drain buffered entries in priority order.

    Example::

        stage = priority_pipeline(transformer, max_size=500, sink=my_sink)
        stage(entry)   # buffered
        stage.flush()  # forwarded highest-priority first
    """
    from fieldlog.pipeline import Pipeline  # local import to avoid cycles

    pstage = PriorityStage(max_size=max_size)

    if stages:
        pipe = Pipeline(list(stages))
        pipe.set_sink(pstage)  # type: ignore[attr-defined]
        pstage.bind(sink)
        return pstage

    pstage.bind(sink)
    return pstage
