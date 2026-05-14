"""Backpressure sink: blocks or drops entries when a downstream sink is overwhelmed."""

from __future__ import annotations

import threading
from typing import Callable, Optional


class BackpressureError(Exception):
    """Raised when backpressure configuration is invalid."""


class Backpressure:
    """Wraps a sink and applies backpressure when the internal queue is full.

    Parameters
    ----------
    sink:
        Downstream callable that receives log entries.
    max_pending:
        Maximum number of entries allowed to queue before applying policy.
    policy:
        ``"drop"`` silently discards new entries when full.
        ``"block"`` blocks the caller until space is available (default).
    timeout:
        Seconds to wait when ``policy="block"`` before raising ``BackpressureError``.
        ``None`` means wait indefinitely.
    """

    def __init__(
        self,
        sink: Callable,
        *,
        max_pending: int = 100,
        policy: str = "drop",
        timeout: Optional[float] = None,
    ) -> None:
        if not callable(sink):
            raise BackpressureError("sink must be callable")
        if max_pending < 1:
            raise BackpressureError("max_pending must be >= 1")
        if policy not in ("drop", "block"):
            raise BackpressureError("policy must be 'drop' or 'block'")

        self._sink = sink
        self._max_pending = max_pending
        self._policy = policy
        self._timeout = timeout
        self._semaphore = threading.Semaphore(max_pending)
        self._dropped = 0
        self._lock = threading.Lock()

    def __call__(self, entry: dict) -> None:
        acquired = self._semaphore.acquire(
            blocking=(self._policy == "block"),
            timeout=self._timeout if self._policy == "block" else None,
        )
        if not acquired:
            if self._policy == "block":
                raise BackpressureError(
                    f"Backpressure timeout after {self._timeout}s: sink not draining"
                )
            with self._lock:
                self._dropped += 1
            return
        try:
            self._sink(entry)
        finally:
            self._semaphore.release()

    @property
    def dropped_count(self) -> int:
        """Total entries dropped due to backpressure."""
        with self._lock:
            return self._dropped

    def reset_stats(self) -> None:
        """Reset the dropped counter."""
        with self._lock:
            self._dropped = 0

    @property
    def policy(self) -> str:
        return self._policy

    @property
    def max_pending(self) -> int:
        return self._max_pending
