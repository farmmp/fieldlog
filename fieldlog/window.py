"""Sliding-window aggregator for log entries.

Groups entries into fixed-duration time windows and forwards a summary
dictionary to a downstream sink when each window closes.
"""

from __future__ import annotations

import time as _time
from typing import Any, Callable, Dict, List, Optional


def _default_clock() -> float:
    return _time.monotonic()


class Window:
    """Accumulate log entries in a rolling time window.

    When *duration* seconds have elapsed since the window opened, the
    window is closed and a summary is forwarded to *sink*.  The summary
    has the shape::

        {
            "window_start": float,
            "window_end":   float,
            "count":        int,
            "entries":      list[dict],
        }

    Parameters
    ----------
    sink:
        Callable that receives the summary dict.
    duration:
        Window length in seconds (must be > 0).
    clock:
        Zero-argument callable returning the current time as a float.
        Defaults to :func:`time.monotonic`.
    """

    def __init__(
        self,
        sink: Callable[[Dict[str, Any]], None],
        duration: float = 60.0,
        *,
        clock: Callable[[], float] = _default_clock,
    ) -> None:
        if not callable(sink):
            raise TypeError("sink must be callable")
        if duration <= 0:
            raise ValueError("duration must be > 0")
        self._sink = sink
        self._duration = duration
        self._clock = clock
        self._entries: List[Dict[str, Any]] = []
        self._window_start: float = self._clock()

    # ------------------------------------------------------------------
    def __call__(self, entry: Dict[str, Any]) -> None:
        """Accept *entry* and flush the window if its duration has elapsed."""
        now = self._clock()
        if now - self._window_start >= self._duration:
            self._flush(now)
        self._entries.append(entry)

    # ------------------------------------------------------------------
    def flush(self) -> None:
        """Force-close the current window immediately."""
        self._flush(self._clock())

    def pending(self) -> int:
        """Return the number of entries in the current (open) window."""
        return len(self._entries)

    # ------------------------------------------------------------------
    def _flush(self, now: float) -> None:
        summary: Dict[str, Any] = {
            "window_start": self._window_start,
            "window_end": now,
            "count": len(self._entries),
            "entries": list(self._entries),
        }
        self._entries.clear()
        self._window_start = now
        self._sink(summary)
