"""Lightweight in-process metrics collector for fieldlog pipeline observability."""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Dict, Iterator, Tuple


class Metrics:
    """Thread-safe counters and gauges for monitoring log pipeline health."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Counters
    # ------------------------------------------------------------------

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment a named counter by *amount* (default 1)."""
        if amount < 0:
            raise ValueError("increment amount must be non-negative")
        with self._lock:
            self._counters[name] += amount

    def counter(self, name: str) -> int:
        """Return the current value of a counter (0 if never incremented)."""
        with self._lock:
            return self._counters[name]

    # ------------------------------------------------------------------
    # Gauges
    # ------------------------------------------------------------------

    def set_gauge(self, name: str, value: float) -> None:
        """Set a named gauge to *value*."""
        with self._lock:
            self._gauges[name] = value

    def gauge(self, name: str) -> float | None:
        """Return the current gauge value, or *None* if not set."""
        with self._lock:
            return self._gauges.get(name)

    # ------------------------------------------------------------------
    # Snapshot / reset
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, object]:
        """Return a point-in-time copy of all counters and gauges."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
            }

    def reset(self) -> None:
        """Clear all counters and gauges."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()

    # ------------------------------------------------------------------
    # Iteration helpers
    # ------------------------------------------------------------------

    def iter_counters(self) -> Iterator[Tuple[str, int]]:
        with self._lock:
            yield from list(self._counters.items())

    def iter_gauges(self) -> Iterator[Tuple[str, float]]:
        with self._lock:
            yield from list(self._gauges.items())
