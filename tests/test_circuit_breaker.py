"""Tests for fieldlog.circuit_breaker."""
from __future__ import annotations

import pytest

from fieldlog.circuit_breaker import CircuitBreaker, CircuitBreakerError


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _entry(**kw) -> dict:
    return {"level": "info", "message": "test", **kw}


class _FakeClock:
    def __init__(self) -> None:
        self._t = 0.0

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


def _failing_sink(entry):
    raise RuntimeError("boom")


def _ok_sink(entry):
    return "ok"


# ---------------------------------------------------------------------------
# construction
# ---------------------------------------------------------------------------

def test_non_callable_raises():
    with pytest.raises(TypeError):
        CircuitBreaker("not-callable")


def test_invalid_max_failures_raises():
    with pytest.raises(ValueError):
        CircuitBreaker(_ok_sink, max_failures=0)


def test_invalid_cooldown_raises():
    with pytest.raises(ValueError):
        CircuitBreaker(_ok_sink, cooldown=0)


# ---------------------------------------------------------------------------
# normal (closed) operation
# ---------------------------------------------------------------------------

def test_initial_state_is_closed():
    cb = CircuitBreaker(_ok_sink)
    assert cb.state == "closed"


def test_successful_call_returns_value():
    cb = CircuitBreaker(_ok_sink)
    assert cb(_entry()) == "ok"


def test_failure_count_increments():
    cb = CircuitBreaker(_failing_sink, max_failures=5)
    for i in range(3):
        with pytest.raises(RuntimeError):
            cb(_entry())
    assert cb.failure_count == 3
    assert cb.state == "closed"


# ---------------------------------------------------------------------------
# tripping open
# ---------------------------------------------------------------------------

def test_trips_open_after_max_failures():
    cb = CircuitBreaker(_failing_sink, max_failures=3)
    for _ in range(3):
        with pytest.raises(RuntimeError):
            cb(_entry())
    assert cb.state == "open"


def test_open_circuit_raises_circuit_breaker_error():
    cb = CircuitBreaker(_failing_sink, max_failures=1)
    with pytest.raises(RuntimeError):
        cb(_entry())
    with pytest.raises(CircuitBreakerError):
        cb(_entry())


# ---------------------------------------------------------------------------
# cooldown / half-open probe
# ---------------------------------------------------------------------------

def test_transitions_to_half_after_cooldown():
    clock = _FakeClock()
    cb = CircuitBreaker(_failing_sink, max_failures=1, cooldown=10.0, clock=clock)
    with pytest.raises(RuntimeError):
        cb(_entry())
    assert cb.state == "open"
    clock.advance(10.0)
    assert cb.state == "half"


def test_successful_probe_closes_circuit():
    clock = _FakeClock()
    cb = CircuitBreaker(_ok_sink, max_failures=1, cooldown=10.0, clock=clock)
    # force open via manual failure count manipulation
    cb._failures = 1
    cb._opened_at = clock()
    cb._state = "open"
    clock.advance(10.0)
    cb(_entry())  # probe succeeds
    assert cb.state == "closed"
    assert cb.failure_count == 0


def test_failed_probe_reopens_circuit():
    clock = _FakeClock()
    cb = CircuitBreaker(_failing_sink, max_failures=1, cooldown=10.0, clock=clock)
    with pytest.raises(RuntimeError):
        cb(_entry())
    clock.advance(10.0)
    assert cb.state == "half"
    with pytest.raises(RuntimeError):
        cb(_entry())
    assert cb.state == "open"


# ---------------------------------------------------------------------------
# manual reset
# ---------------------------------------------------------------------------

def test_manual_reset_closes_circuit():
    cb = CircuitBreaker(_failing_sink, max_failures=1)
    with pytest.raises(RuntimeError):
        cb(_entry())
    assert cb.state == "open"
    cb.reset()
    assert cb.state == "closed"
    assert cb.failure_count == 0


def test_success_resets_failure_count():
    cb = CircuitBreaker(_ok_sink, max_failures=5)
    cb._failures = 3
    cb(_entry())
    assert cb.failure_count == 0
