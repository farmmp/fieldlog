"""Pipeline integration helpers for Aggregator."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from fieldlog.aggregator import Aggregator, _Clock, _default_clock
from fieldlog.pipeline import Pipeline

_Sink = Callable[[Dict[str, Any]], None]


class AggregatorStage:
    """Wraps an :class:`~fieldlog.aggregator.Aggregator` for use in a
    :class:`~fieldlog.pipeline.Pipeline` chain.

    The stage passes every entry through to *downstream* unchanged **and**
    feeds a copy into the aggregator.  When the aggregation window closes the
    summary is forwarded to *summary_sink*.

    Parameters
    ----------
    downstream:
        Next stage / sink that receives the original entries.
    summary_sink:
        Sink that receives aggregation summaries.  Defaults to *downstream*.
    interval:
        Aggregation window in seconds.
    key_field:
        Entry field used to group counts.
    clock:
        Injectable clock for testing.
    """

    def __init__(
        self,
        downstream: _Sink,
        summary_sink: Optional[_Sink] = None,
        interval: float = 60.0,
        key_field: str = "level",
        clock: _Clock = _default_clock,
    ) -> None:
        if not callable(downstream):
            raise TypeError("downstream must be callable")
        self._downstream = downstream
        self._aggregator = Aggregator(
            sink=summary_sink if summary_sink is not None else downstream,
            interval=interval,
            key_field=key_field,
            clock=clock,
        )

    def bind(self, sink: _Sink) -> "AggregatorStage":
        """Return a new stage bound to *sink* as downstream."""
        return AggregatorStage(
            downstream=sink,
            summary_sink=self._aggregator._sink,
            interval=self._aggregator._interval,
            key_field=self._aggregator._key_field,
            clock=self._aggregator._clock,
        )

    def __call__(self, entry: Dict[str, Any]) -> None:
        self._aggregator(entry)
        self._downstream(entry)

    @property
    def dropped_count(self) -> int:  # kept for pipeline API parity
        return 0


def aggregator_pipeline(
    sink: _Sink,
    summary_sink: Optional[_Sink] = None,
    interval: float = 60.0,
    key_field: str = "level",
    clock: _Clock = _default_clock,
) -> Pipeline:
    """Return a :class:`~fieldlog.pipeline.Pipeline` with an aggregator stage."""
    stage = AggregatorStage(
        downstream=sink,
        summary_sink=summary_sink,
        interval=interval,
        key_field=key_field,
        clock=clock,
    )
    return Pipeline(sink=stage)
