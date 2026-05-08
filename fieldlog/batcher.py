"""
Batcher: accumulates log entries and flushes them as a batch
to a downstream sink once a size or time threshold is reached.
"""

import time
from typing import Callable, List, Optional


_Clock = Callable[[], float]


class Batcher:
    """
    Collects log entries into batches and forwards them to a sink
    when either *max_size* entries have accumulated or *max_age_seconds*
    have elapsed since the first entry in the current batch.

    Parameters
    ----------
    sink:
        Callable that receives a list of log-entry dicts.
    max_size:
        Maximum number of entries before an automatic flush.
    max_age_seconds:
        Maximum seconds a batch may sit before being flushed.
    clock:
        Callable returning current time as a float (default: time.monotonic).
    """

    def __init__(
        self,
        sink: Callable[[List[dict]], None],
        *,
        max_size: int = 50,
        max_age_seconds: float = 5.0,
        clock: Optional[_Clock] = None,
    ) -> None:
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        if max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be > 0")

        self._sink = sink
        self._max_size = max_size
        self._max_age = max_age_seconds
        self._clock = clock or time.monotonic

        self._batch: List[dict] = []
        self._batch_start: Optional[float] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def __call__(self, entry: dict) -> None:
        """Accept a single log entry."""
        if self._batch_start is None:
            self._batch_start = self._clock()

        self._batch.append(entry)

        if self._should_flush():
            self.flush()

    def flush(self) -> int:
        """Immediately flush whatever is buffered.  Returns number of entries sent."""
        if not self._batch:
            return 0
        batch, self._batch = self._batch, []
        self._batch_start = None
        self._sink(batch)
        return len(batch)

    @property
    def pending(self) -> int:
        """Number of entries waiting in the current batch."""
        return len(self._batch)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _should_flush(self) -> bool:
        if len(self._batch) >= self._max_size:
            return True
        if self._batch_start is not None:
            age = self._clock() - self._batch_start
            if age >= self._max_age:
                return True
        return False
