"""Tests for fieldlog.ratelimiter.RateLimiter."""

import pytest
from fieldlog.ratelimiter import RateLimiter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(level="INFO", tag="sensor", msg="reading", **extra):
    return {"level": level, "tag": tag, "msg": msg, **extra}


class _FakeClock:
    def __init__(self, start: float = 0.0):
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_negative_window_raises():
    with pytest.raises(ValueError):
        RateLimiter(window_seconds=-1)


def test_zero_window_always_passes():
    clock = _FakeClock()
    rl = RateLimiter(window_seconds=0, clock=clock)
    e = _entry()
    assert rl(e) is not None
    assert rl(e) is not None  # same tick, window=0 → always >= 0


# ---------------------------------------------------------------------------
# Basic allow / suppress behaviour
# ---------------------------------------------------------------------------

def test_first_entry_always_passes():
    clock = _FakeClock()
    rl = RateLimiter(window_seconds=5, clock=clock)
    result = rl(_entry())
    assert result is not None


def test_second_entry_within_window_is_dropped():
    clock = _FakeClock()
    rl = RateLimiter(window_seconds=5, clock=clock)
    rl(_entry())
    clock.advance(3)
    assert rl(_entry()) is None


def test_entry_passes_after_window_expires():
    clock = _FakeClock()
    rl = RateLimiter(window_seconds=5, clock=clock)
    rl(_entry())
    clock.advance(5)
    assert rl(_entry()) is not None


# ---------------------------------------------------------------------------
# Suppression counter annotation
# ---------------------------------------------------------------------------

def test_suppressed_count_annotated_on_next_pass():
    clock = _FakeClock()
    rl = RateLimiter(window_seconds=5, clock=clock)
    rl(_entry())           # pass-through, counter = 0
    clock.advance(1)
    rl(_entry())           # suppressed (count → 1)
    clock.advance(1)
    rl(_entry())           # suppressed (count → 2)
    clock.advance(10)      # window expired
    result = rl(_entry())  # should pass with _suppressed=2
    assert result is not None
    assert result["_suppressed"] == 2


def test_no_suppressed_annotation_when_none_dropped():
    clock = _FakeClock()
    rl = RateLimiter(window_seconds=5, clock=clock)
    result = rl(_entry())
    assert "_suppressed" not in result


# ---------------------------------------------------------------------------
# Key isolation
# ---------------------------------------------------------------------------

def test_different_keys_are_independent():
    clock = _FakeClock()
    rl = RateLimiter(window_seconds=5, clock=clock)
    rl(_entry(tag="a"))
    # tag="b" is a different key — should pass even though window is open
    assert rl(_entry(tag="b")) is not None


# ---------------------------------------------------------------------------
# Custom key function
# ---------------------------------------------------------------------------

def test_custom_key_fn():
    clock = _FakeClock()
    rl = RateLimiter(window_seconds=5, key_fn=lambda e: e["msg"], clock=clock)
    rl(_entry(msg="boom"))
    clock.advance(2)
    # Same msg → suppressed
    assert rl(_entry(msg="boom", tag="other")) is None
    # Different msg → passes
    assert rl(_entry(msg="ok")) is not None


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def test_reset_clears_state():
    clock = _FakeClock()
    rl = RateLimiter(window_seconds=5, clock=clock)
    rl(_entry())
    clock.advance(1)
    assert rl(_entry()) is None  # suppressed
    rl.reset()
    assert rl(_entry()) is not None  # passes after reset
