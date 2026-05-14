"""Tests for fieldlog.pipeline_circuit_breaker."""
from __future__ import annotations

import pytest

from fieldlog.circuit_breaker import CircuitBreakerError
from fieldlog.pipeline_circuit_breaker import CircuitBreakerStage, circuit_breaker_pipeline


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _entry(**kw) -> dict:
    return {"level": "info", "message": "hello", **kw}


class _FakeClock:
    def __init__(self) -> None:
        self._t = 0.0

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


# ---------------------------------------------------------------------------
# CircuitBreakerStage – unbound guard
# ---------------------------------------------------------------------------

def test_unbound_stage_raises_on_call():
    stage = CircuitBreakerStage()
    with pytest.raises(RuntimeError, match="not been bound"):
        stage(_entry())


def test_unbound_state_is_unbound():
    stage = CircuitBreakerStage()
    assert stage.state == "unbound"


# ---------------------------------------------------------------------------
# CircuitBreakerStage – normal operation
# ---------------------------------------------------------------------------

def test_stage_forwards_to_sink():
    collected = []
    stage = CircuitBreakerStage()
    stage.bind(collected.append)
    stage(_entry())
    assert len(collected) == 1


def test_stage_trips_open_after_max_failures():
    def bad_sink(e):
        raise RuntimeError("oops")

    stage = CircuitBreakerStage(max_failures=2)
    stage.bind(bad_sink)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            stage(_entry())
    assert stage.state == "open"


def test_open_stage_does_not_raise_by_default():
    """Without a fallback the stage silently swallows CircuitBreakerError."""
    def bad_sink(e):
        raise RuntimeError("oops")

    stage = CircuitBreakerStage(max_failures=1)
    stage.bind(bad_sink)
    with pytest.raises(RuntimeError):
        stage(_entry())  # trips open
    # second call: circuit open, no exception propagated
    stage(_entry())
    assert stage.state == "open"


def test_open_stage_routes_to_fallback():
    fallback_collected = []

    def bad_sink(e):
        raise RuntimeError("oops")

    stage = CircuitBreakerStage(max_failures=1, fallback=fallback_collected.append)
    stage.bind(bad_sink)
    with pytest.raises(RuntimeError):
        stage(_entry())
    stage(_entry())  # open – goes to fallback
    assert len(fallback_collected) == 1


# ---------------------------------------------------------------------------
# CircuitBreakerStage – cooldown / reset
# ---------------------------------------------------------------------------

def test_stage_resets_manually():
    collected = []

    def bad_sink(e):
        raise RuntimeError("oops")

    stage = CircuitBreakerStage(max_failures=1)
    stage.bind(bad_sink)
    with pytest.raises(RuntimeError):
        stage(_entry())
    assert stage.state == "open"
    stage.reset()
    assert stage.state == "closed"
    assert stage.failure_count == 0


def test_stage_transitions_half_after_cooldown():
    clock = _FakeClock()
    collected = []

    def bad_sink(e):
        raise RuntimeError("oops")

    stage = CircuitBreakerStage(max_failures=1, cooldown=5.0, clock=clock)
    stage.bind(bad_sink)
    with pytest.raises(RuntimeError):
        stage(_entry())
    clock.advance(5.0)
    assert stage.state == "half"


# ---------------------------------------------------------------------------
# circuit_breaker_pipeline convenience helper
# ---------------------------------------------------------------------------

def test_pipeline_helper_returns_pipeline_like():
    collected = []
    p = circuit_breaker_pipeline(collected.append, max_failures=3, cooldown=60.0)
    # Pipeline exposes a __call__ forwarding to the source stage
    assert callable(p)


def test_pipeline_helper_forwards_entries():
    collected = []
    p = circuit_breaker_pipeline(collected.append)
    p.source(_entry())
    assert len(collected) == 1
