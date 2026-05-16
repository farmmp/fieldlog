"""Priority-aware log queue that reorders entries by level before forwarding."""

from __future__ import annotations

import heapq
from typing import Any, Callable, Dict, List, Optional

# Numeric priority: lower number = higher urgency
_LEVEL_PRIORITY: Dict[str, int] = {
    "critical": 0,
    "error": 1,
    "warning": 2,
    "info": 3,
    "debug": 4,
}

_DEFAULT_PRIORITY = 3  # treat unknown levels as "info"


class PriorityQueueError(Exception):
    """Raised for configuration errors in PriorityQueue."""


class PriorityQueue:
    """Buffers log entries and flushes them ordered by level priority.

    Args:
        sink: Callable that receives a single log-entry dict.
        max_size: Maximum number of entries buffered before the oldest
                  *lowest-priority* entry is evicted. 0 means unbounded.
    """

    def __init__(self, sink: Callable[[Dict[str, Any]], None], max_size: int = 0) -> None:
        if not callable(sink):
            raise PriorityQueueError("sink must be callable")
        if max_size < 0:
            raise PriorityQueueError("max_size must be >= 0")
        self._sink = sink
        self._max_size = max_size
        self._heap: List[tuple] = []  # (priority, counter, entry)
        self._counter = 0
        self._dropped = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def __call__(self, entry: Dict[str, Any]) -> None:
        """Accept an entry into the priority buffer."""
        level = str(entry.get("level", "")).lower()
        priority = _LEVEL_PRIORITY.get(level, _DEFAULT_PRIORITY)
        heapq.heappush(self._heap, (priority, self._counter, entry))
        self._counter += 1
        if self._max_size and len(self._heap) > self._max_size:
            self._evict_lowest_priority()

    def flush(self) -> int:
        """Forward all buffered entries to the sink, highest priority first.

        Returns:
            Number of entries forwarded.
        """
        count = 0
        while self._heap:
            _, _, entry = heapq.heappop(self._heap)
            self._sink(entry)
            count += 1
        return count

    @property
    def pending(self) -> int:
        """Number of entries currently buffered."""
        return len(self._heap)

    @property
    def dropped_count(self) -> int:
        """Number of entries evicted due to max_size overflow."""
        return self._dropped

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evict_lowest_priority(self) -> None:
        """Remove the entry with the *lowest* urgency (highest priority number)."""
        # Convert to list, remove worst, re-heapify
        worst_idx = max(range(len(self._heap)), key=lambda i: (self._heap[i][0], -self._heap[i][1]))
        self._heap.pop(worst_idx)
        heapq.heapify(self._heap)
        self._dropped += 1
