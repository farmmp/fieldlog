"""Wraps any callable sink to record per-sink metrics via a Metrics instance."""
from __future__ import annotations

from typing import Any, Callable, Dict

from fieldlog.metrics import Metrics

SinkCallable = Callable[[Dict[str, Any]], None]


class InstrumentedSink:
    """Decorator that counts accepted, dropped, and errored log entries.

    Parameters
    ----------
    sink:
        The downstream sink to forward entries to.
    metrics:
        Shared :class:`Metrics` instance used to record observations.
    name:
        Logical name for this sink; used as a prefix for metric keys.
    """

    def __init__(self, sink: SinkCallable, metrics: Metrics, name: str) -> None:
        if not callable(sink):
            raise TypeError("sink must be callable")
        self._sink = sink
        self._metrics = metrics
        self._name = name

    # ------------------------------------------------------------------
    # Metric key helpers
    # ------------------------------------------------------------------

    def _key(self, suffix: str) -> str:
        return f"sink.{self._name}.{suffix}"

    # ------------------------------------------------------------------
    # Sink protocol
    # ------------------------------------------------------------------

    def __call__(self, entry: Dict[str, Any]) -> None:
        """Forward *entry* to the wrapped sink and update counters."""
        try:
            self._sink(entry)
            self._metrics.increment(self._key("accepted"))
        except Exception:
            self._metrics.increment(self._key("errors"))
            raise

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    def accepted(self) -> int:
        return self._metrics.counter(self._key("accepted"))

    def errors(self) -> int:
        return self._metrics.counter(self._key("errors"))
