"""Circuit breaker sink wrapper for fieldlog.

Trips open after a configurable number of consecutive failures,
then allows a single probe after a cooldown period before resetting.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

_default_clock: Callable[[], float] = time.monotonic


class CircuitBreakerError(Exception):
    """Raised when the circuit is open and a call is attempted."""


class CircuitBreaker:
    """Wraps a sink and opens the circuit after *max_failures* consecutive errors.

    States
    ------
    closed  – normal operation; failures are counted.
    open    – sink is not called; CircuitBreakerError is raised.
    half    – one probe attempt is allowed after *cooldown* seconds.
    """

    def __init__(
        self,
        sink: Callable[[dict], Any],
        *,
        max_failures: int = 3,
        cooldown: float = 30.0,
        clock: Callable[[], float] = _default_clock,
    ) -> None:
        if not callable(sink):
            raise TypeError("sink must be callable")
        if max_failures < 1:
            raise ValueError("max_failures must be >= 1")
        if cooldown <= 0:
            raise ValueError("cooldown must be > 0")

        self._sink = sink
        self._max_failures = max_failures
        self._cooldown = cooldown
        self._clock = clock

        self._failures = 0
        self._opened_at: Optional[float] = None
        self._state = "closed"  # closed | open | half

    # ------------------------------------------------------------------
    # public interface
    # ------------------------------------------------------------------

    def __call__(self, entry: dict) -> Any:
        self._maybe_transition()
        if self._state == "open":
            raise CircuitBreakerError("circuit is open")
        try:
            result = self._sink(entry)
            self._on_success()
            return result
        except CircuitBreakerError:
            raise
        except Exception:
            self._on_failure()
            raise

    @property
    def state(self) -> str:
        self._maybe_transition()
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failures

    def reset(self) -> None:
        """Manually close the circuit and clear failure count."""
        self._failures = 0
        self._opened_at = None
        self._state = "closed"

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _maybe_transition(self) -> None:
        if self._state == "open" and self._opened_at is not None:
            if self._clock() - self._opened_at >= self._cooldown:
                self._state = "half"

    def _on_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._state = "closed"

    def _on_failure(self) -> None:
        self._failures += 1
        if self._state == "half" or self._failures >= self._max_failures:
            self._opened_at = self._clock()
            self._state = "open"
