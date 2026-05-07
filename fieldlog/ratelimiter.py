"""
Rate limiter for fieldlog — suppresses repeated log entries within a time window.
Useful on edge devices to avoid flooding storage or uplinks with burst events.
"""

import time
from collections import defaultdict
from typing import Any, Callable, Dict, Optional, Tuple


class RateLimiter:
    """
    Limits how often entries with the same key are passed through.

    The key is derived from each log entry via a ``key_fn`` callable.
    If an entry's key has been seen within ``window_seconds``, it is dropped.
    Once the window expires the entry is allowed through again.

    Parameters
    ----------
    window_seconds:
        Minimum seconds that must pass before the same key is forwarded again.
    key_fn:
        Callable that receives a log-entry dict and returns a hashable key.
        Defaults to ``(level, tag)`` tuple.
    clock:
        Callable returning the current time as a float (seconds).  Defaults to
        ``time.monotonic``.  Inject a fake clock in tests.
    """

    def __init__(
        self,
        window_seconds: float,
        key_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if window_seconds < 0:
            raise ValueError("window_seconds must be >= 0")
        self._window = window_seconds
        self._key_fn = key_fn or self._default_key
        self._clock = clock
        # key -> (last_allowed_time, suppressed_count)
        self._seen: Dict[Any, Tuple[float, int]] = defaultdict(lambda: (-float("inf"), 0))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def __call__(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return the entry if it should be forwarded, else ``None``."""
        key = self._key_fn(entry)
        now = self._clock()
        last_time, suppressed = self._seen[key]

        if now - last_time >= self._window:
            # Annotate with how many were suppressed since last pass-through
            if suppressed:
                entry = dict(entry, _suppressed=suppressed)
            self._seen[key] = (now, 0)
            return entry

        # Within window — drop and increment suppression counter
        self._seen[key] = (last_time, suppressed + 1)
        return None

    def reset(self) -> None:
        """Clear all recorded keys and counters."""
        self._seen.clear()

    def suppressed_count(self, entry: Dict[str, Any]) -> int:
        """Return the current suppression counter for an entry's key."""
        key = self._key_fn(entry)
        return self._seen[key][1]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _default_key(entry: Dict[str, Any]) -> Tuple[Any, Any]:
        return (entry.get("level"), entry.get("tag"))
