"""Dead-letter queue for log entries that could not be delivered."""

from __future__ import annotations

from collections import deque
from typing import Callable, Deque, Iterable, Optional
import time


class DeadLetterQueue:
    """Stores entries that failed delivery for later inspection or replay.

    Args:
        maxlen: Maximum number of failed entries to retain (oldest evicted first).
        clock: Callable returning current epoch timestamp (injectable for testing).
    """

    def __init__(
        self,
        maxlen: int = 256,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if maxlen < 1:
            raise ValueError("maxlen must be >= 1")
        self._maxlen = maxlen
        self._clock = clock
        self._queue: Deque[dict] = deque(maxlen=maxlen)

    # ------------------------------------------------------------------
    # Sink interface
    # ------------------------------------------------------------------

    def __call__(self, entry: dict, exc: Optional[Exception] = None) -> None:
        """Record a failed entry (compatible with RetrySink on_failure signature)."""
        record = dict(entry)
        record["_dlq_ts"] = self._clock()
        if exc is not None:
            record["_dlq_error"] = str(exc)
        self._queue.append(record)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._queue)

    def __iter__(self):
        return iter(list(self._queue))

    def peek(self, n: int = 10) -> list[dict]:
        """Return up to *n* oldest entries without removing them."""
        items = list(self._queue)
        return items[:n]

    # ------------------------------------------------------------------
    # Replay / drain
    # ------------------------------------------------------------------

    def drain(self, sink: Callable[[dict], None]) -> int:
        """Replay all queued entries through *sink*, clearing the queue.

        Returns:
            Number of entries replayed.
        """
        replayed = 0
        while self._queue:
            entry = self._queue.popleft()
            # Strip DLQ metadata before replaying
            clean = {k: v for k, v in entry.items() if not k.startswith("_dlq_")}
            sink(clean)
            replayed += 1
        return replayed

    def clear(self) -> None:
        """Discard all queued entries."""
        self._queue.clear()

    @property
    def maxlen(self) -> int:
        """Maximum capacity of the dead-letter queue."""
        return self._maxlen
