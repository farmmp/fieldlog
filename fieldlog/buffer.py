"""Ring buffer for storing log entries in memory on edge devices."""

from collections import deque
from threading import Lock
from typing import Any, Dict, Iterator, List, Optional


class LogBuffer:
    """Thread-safe ring buffer for log entries with a configurable max size."""

    def __init__(self, maxsize: int = 1000) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        self._maxsize = maxsize
        self._buffer: deque = deque(maxlen=maxsize)
        self._lock = Lock()
        self._dropped: int = 0

    def push(self, entry: Dict[str, Any]) -> bool:
        """Add a log entry. Returns False if an old entry was evicted."""
        with self._lock:
            evicted = len(self._buffer) == self._maxsize
            if evicted:
                self._dropped += 1
            self._buffer.append(entry)
            return not evicted

    def flush(self, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """Remove and return up to `count` entries (all if count is None)."""
        with self._lock:
            if count is None:
                items = list(self._buffer)
                self._buffer.clear()
            else:
                items = [self._buffer.popleft() for _ in range(min(count, len(self._buffer)))]
            return items

    def peek(self, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return entries without removing them."""
        with self._lock:
            items = list(self._buffer)
            return items if count is None else items[:count]

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        with self._lock:
            snapshot = list(self._buffer)
        return iter(snapshot)

    @property
    def maxsize(self) -> int:
        return self._maxsize

    @property
    def dropped(self) -> int:
        """Total number of entries evicted due to buffer overflow."""
        with self._lock:
            return self._dropped

    @property
    def is_full(self) -> bool:
        with self._lock:
            return len(self._buffer) == self._maxsize

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()
