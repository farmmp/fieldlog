"""Aggregator: collects log entries over a window and emits summary records."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

_Sink = Callable[[Dict[str, Any]], None]
_Clock = Callable[[], float]


def _default_clock() -> float:
    return time.monotonic()


class Aggregator:
    """Accumulate entries for *interval* seconds, then emit a summary entry.

    Parameters
    ----------
    sink:
        Downstream callable that receives the aggregated summary dict.
    interval:
        Window length in seconds.  When the window closes the summary is
        flushed automatically on the next call.
    key_field:
        Entry field used to group counts (default: ``"level"``).
    clock:
        Callable returning current time (injectable for testing).
    """

    def __init__(
        self,
        sink: _Sink,
        interval: float = 60.0,
        key_field: str = "level",
        clock: _Clock = _default_clock,
    ) -> None:
        if not callable(sink):
            raise TypeError("sink must be callable")
        if interval <= 0:
            raise ValueError("interval must be positive")
        self._sink = sink
        self._interval = interval
        self._key_field = key_field
        self._clock = clock
        self._counts: Dict[str, int] = defaultdict(int)
        self._total: int = 0
        self._window_start: float = self._clock()

    # ------------------------------------------------------------------
    def __call__(self, entry: Dict[str, Any]) -> None:
        now = self._clock()
        if now - self._window_start >= self._interval:
            self.flush()
        key = str(entry.get(self._key_field, "unknown"))
        self._counts[key] += 1
        self._total += 1

    # ------------------------------------------------------------------
    def flush(self) -> None:
        """Emit the current summary and reset counters."""
        now = self._clock()
        summary: Dict[str, Any] = {
            "type": "aggregation_summary",
            "window_start": self._window_start,
            "window_end": now,
            "interval": self._interval,
            "total": self._total,
            "counts": dict(self._counts),
        }
        self._sink(summary)
        self._counts = defaultdict(int)
        self._total = 0
        self._window_start = now

    # ------------------------------------------------------------------
    @property
    def pending(self) -> int:
        """Number of entries accumulated since the last flush."""
        return self._total
