"""
Throttle: time-window-based rate limiting that allows at most N entries
per key (e.g. tag or level) within a rolling time window.
"""

import time
from collections import defaultdict, deque
from typing import Callable, Optional


def _default_clock() -> float:
    return time.monotonic()


class Throttle:
    """
    Allows at most *limit* log entries per *window* seconds for each key.

    The key is derived from an entry by *key_fn* (default: ``level``).
    Entries that exceed the limit are silently dropped; a count of
    dropped entries is kept per key.

    Parameters
    ----------
    limit:   maximum entries allowed per window per key.
    window:  rolling window size in seconds.
    sink:    downstream callable that receives allowed entries.
    key_fn:  callable(entry) -> hashable; defaults to entry["level"].
    clock:   callable returning current time (injectable for tests).
    """

    def __init__(
        self,
        limit: int,
        window: float,
        sink: Callable,
        key_fn: Optional[Callable] = None,
        clock: Callable[[], float] = _default_clock,
    ) -> None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if window <= 0:
            raise ValueError("window must be > 0")
        if not callable(sink):
            raise TypeError("sink must be callable")

        self._limit = limit
        self._window = window
        self._sink = sink
        self._key_fn = key_fn or (lambda e: e.get("level", ""))
        self._clock = clock
        # key -> deque of timestamps for entries that passed
        self._buckets: dict[object, deque] = defaultdict(deque)
        self._dropped: dict[object, int] = defaultdict(int)

    def __call__(self, entry: dict) -> None:
        key = self._key_fn(entry)
        now = self._clock()
        bucket = self._buckets[key]

        # Evict timestamps outside the rolling window
        cutoff = now - self._window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) < self._limit:
            bucket.append(now)
            self._sink(entry)
        else:
            self._dropped[key] += 1

    def dropped_count(self, key: object = None) -> int:
        """Return total dropped entries, optionally filtered by key."""
        if key is not None:
            return self._dropped[key]
        return sum(self._dropped.values())

    def reset(self) -> None:
        """Clear all buckets and drop counters."""
        self._buckets.clear()
        self._dropped.clear()
