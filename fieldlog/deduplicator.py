"""Deduplicator: suppress repeated log entries within a time window."""

import hashlib
import time
from typing import Callable, Optional


def _default_clock() -> float:
    return time.monotonic()


def _entry_fingerprint(entry: dict) -> str:
    """Produce a stable hash from level + message (+ optional tag)."""
    level = entry.get("level", "")
    message = entry.get("message", "")
    tag = entry.get("tag", "")
    raw = f"{level}:{tag}:{message}"
    return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()


class Deduplicator:
    """Drop duplicate log entries seen within *window_seconds*.

    Two entries are considered duplicates when they share the same
    level, message, and tag (if present).  The first occurrence is
    always forwarded; subsequent identical entries within the window
    are suppressed.  After the window expires the entry is allowed
    through again and the window resets.

    Parameters
    ----------
    sink:
        Callable that receives accepted entries.
    window_seconds:
        Deduplication window in seconds (default 60).
    clock:
        Optional callable returning current time (injectable for tests).
    """

    def __init__(
        self,
        sink: Callable[[dict], None],
        window_seconds: float = 60.0,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._sink = sink
        self._window = window_seconds
        self._clock = clock or _default_clock
        # fingerprint -> timestamp of first occurrence in current window
        self._seen: dict[str, float] = {}
        self._suppressed = 0

    def __call__(self, entry: dict) -> None:
        fp = _entry_fingerprint(entry)
        now = self._clock()
        first_seen = self._seen.get(fp)
        if first_seen is None or (now - first_seen) >= self._window:
            self._seen[fp] = now
            self._sink(entry)
        else:
            self._suppressed += 1

    @property
    def suppressed_count(self) -> int:
        """Total number of entries suppressed since creation."""
        return self._suppressed

    def reset(self) -> None:
        """Clear all tracked fingerprints and reset the suppressed counter."""
        self._seen.clear()
        self._suppressed = 0
