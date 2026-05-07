"""Retry sink wrapper for resilient log delivery in low-connectivity environments."""

from __future__ import annotations

import time
from typing import Callable, Optional


SinkFn = Callable[[dict], None]


class RetryError(Exception):
    """Raised when all retry attempts for a log entry are exhausted."""


class RetrySink:
    """Wraps a sink function with configurable retry logic and backoff.

    Args:
        sink: The underlying sink callable to deliver entries to.
        max_attempts: Total number of delivery attempts (including the first).
        backoff_base: Base delay in seconds between retries.
        backoff_factor: Multiplier applied to delay on each subsequent attempt.
        max_delay: Maximum delay cap in seconds.
        on_failure: Optional callback invoked with (entry, exception) on final failure.
        clock: Callable returning current time (injectable for testing).
        sleep: Callable used for sleeping between retries (injectable for testing).
    """

    def __init__(
        self,
        sink: SinkFn,
        max_attempts: int = 3,
        backoff_base: float = 0.5,
        backoff_factor: float = 2.0,
        max_delay: float = 30.0,
        on_failure: Optional[Callable[[dict, Exception], None]] = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self._sink = sink
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._backoff_factor = backoff_factor
        self._max_delay = max_delay
        self._on_failure = on_failure
        self._clock = clock
        self._sleep = sleep
        self._total_attempts = 0
        self._total_failures = 0

    def __call__(self, entry: dict) -> None:
        """Attempt to deliver entry, retrying on exception."""
        delay = self._backoff_base
        last_exc: Optional[Exception] = None

        for attempt in range(self._max_attempts):
            self._total_attempts += 1
            try:
                self._sink(entry)
                return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self._max_attempts - 1:
                    self._sleep(min(delay, self._max_delay))
                    delay *= self._backoff_factor

        self._total_failures += 1
        if self._on_failure is not None:
            self._on_failure(entry, last_exc)  # type: ignore[arg-type]
        else:
            raise RetryError(
                f"Delivery failed after {self._max_attempts} attempts"
            ) from last_exc

    @property
    def total_attempts(self) -> int:
        """Cumulative number of sink call attempts."""
        return self._total_attempts

    @property
    def total_failures(self) -> int:
        """Number of entries that exhausted all retry attempts."""
        return self._total_failures

    def reset_stats(self) -> None:
        """Reset attempt and failure counters."""
        self._total_attempts = 0
        self._total_failures = 0
