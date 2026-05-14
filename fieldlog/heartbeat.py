"""Heartbeat sink — emits a periodic alive signal if no entries flow through.

Useful on edge devices where silence might mean the pipeline has stalled.
The heartbeat entry is forwarded to the wrapped sink on each __call__ if
the configured interval has elapsed without a real entry being seen.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

_Sink = Callable[[Dict[str, Any]], None]


def _default_clock() -> float:
    return time.monotonic()


class HeartbeatError(Exception):
    """Raised when Heartbeat is misconfigured."""


class Heartbeat:
    """Wraps a sink and injects a synthetic heartbeat entry when idle.

    Parameters
    ----------
    sink:
        Downstream callable that receives log entries.
    interval:
        Seconds of silence after which a heartbeat entry is emitted.
    tag:
        Tag attached to heartbeat entries (default ``"heartbeat"``).
    clock:
        Callable returning current monotonic time; injectable for tests.
    """

    def __init__(
        self,
        sink: _Sink,
        interval: float,
        *,
        tag: str = "heartbeat",
        clock: Callable[[], float] = _default_clock,
    ) -> None:
        if not callable(sink):
            raise HeartbeatError("sink must be callable")
        if interval <= 0:
            raise HeartbeatError("interval must be a positive number")

        self._sink = sink
        self._interval = interval
        self._tag = tag
        self._clock = clock
        self._last_seen: float = clock()
        self._heartbeats_emitted: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def __call__(self, entry: Dict[str, Any]) -> None:
        """Forward *entry* and reset the idle timer."""
        self._last_seen = self._clock()
        self._sink(entry)

    def tick(self) -> bool:
        """Check idle time; emit a heartbeat if the interval has elapsed.

        Returns ``True`` if a heartbeat was emitted, ``False`` otherwise.
        Call this from a background loop or a scheduler.
        """
        now = self._clock()
        if now - self._last_seen >= self._interval:
            self._emit_heartbeat(now)
            return True
        return False

    @property
    def heartbeats_emitted(self) -> int:
        """Total number of heartbeat entries injected so far."""
        return self._heartbeats_emitted

    @property
    def idle_seconds(self) -> float:
        """Seconds elapsed since the last real entry was received."""
        return self._clock() - self._last_seen

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit_heartbeat(self, now: float) -> None:
        self._heartbeats_emitted += 1
        self._last_seen = now
        self._sink(
            {
                "level": "DEBUG",
                "tag": self._tag,
                "message": "heartbeat",
                "heartbeat_index": self._heartbeats_emitted,
            }
        )
