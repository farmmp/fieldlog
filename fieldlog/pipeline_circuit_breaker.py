"""Pipeline integration for CircuitBreaker.

Provides :class:`CircuitBreakerStage` for use with :class:`~fieldlog.pipeline.Pipeline`
and the convenience helper :func:`circuit_breaker_pipeline`.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

from fieldlog.circuit_breaker import CircuitBreaker, CircuitBreakerError
from fieldlog.pipeline import Pipeline


class CircuitBreakerStage:
    """A pipeline stage that wraps a downstream sink with a :class:`CircuitBreaker`.

    Entries that hit an open circuit are forwarded to *fallback* (if provided)
    instead of being silently dropped.
    """

    def __init__(
        self,
        *,
        max_failures: int = 3,
        cooldown: float = 30.0,
        fallback: Optional[Callable[[dict], Any]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_failures = max_failures
        self._cooldown = cooldown
        self._fallback = fallback
        self._clock = clock
        self._breaker: Optional[CircuitBreaker] = None

    # ------------------------------------------------------------------
    # Pipeline protocol
    # ------------------------------------------------------------------

    def bind(self, sink: Callable[[dict], Any]) -> "CircuitBreakerStage":
        """Attach the downstream *sink*; returns *self* for chaining."""
        self._breaker = CircuitBreaker(
            sink,
            max_failures=self._max_failures,
            cooldown=self._cooldown,
            clock=self._clock,
        )
        return self

    def __call__(self, entry: dict) -> Any:
        if self._breaker is None:
            raise RuntimeError("CircuitBreakerStage has not been bound to a sink")
        try:
            return self._breaker(entry)
        except CircuitBreakerError:
            if self._fallback is not None:
                return self._fallback(entry)

    # ------------------------------------------------------------------
    # convenience accessors
    # ------------------------------------------------------------------

    @property
    def state(self) -> str:
        if self._breaker is None:
            return "unbound"
        return self._breaker.state

    @property
    def failure_count(self) -> int:
        return self._breaker.failure_count if self._breaker else 0

    def reset(self) -> None:
        if self._breaker is not None:
            self._breaker.reset()


def circuit_breaker_pipeline(
    sink: Callable[[dict], Any],
    *,
    max_failures: int = 3,
    cooldown: float = 30.0,
    fallback: Optional[Callable[[dict], Any]] = None,
    clock: Callable[[], float] = time.monotonic,
) -> Pipeline:
    """Return a :class:`~fieldlog.pipeline.Pipeline` with a circuit-breaker stage.

    Parameters
    ----------
    sink:         The downstream sink to protect.
    max_failures: Consecutive failures before the circuit opens.
    cooldown:     Seconds before a half-open probe is attempted.
    fallback:     Optional sink called when the circuit is open.
    clock:        Monotonic clock callable (injectable for testing).
    """
    stage = CircuitBreakerStage(
        max_failures=max_failures,
        cooldown=cooldown,
        fallback=fallback,
        clock=clock,
    )
    stage.bind(sink)
    return Pipeline(source=stage, sink=stage)
