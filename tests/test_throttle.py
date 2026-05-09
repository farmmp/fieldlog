"""
Tests for fieldlog.throttle.Throttle
"""

import pytest
from fieldlog.throttle import Throttle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(level="info", msg="hello", **kw):
    return {"level": level, "msg": msg, **kw}


class _FakeClock:
    def __init__(self, start: float = 0.0):
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


@pytest.fixture
def collected():
    return []


@pytest.fixture
def clock():
    return _FakeClock()


# ---------------------------------------------------------------------------
# Construction guards
# ---------------------------------------------------------------------------

def test_invalid_limit_raises(collected):
    with pytest.raises(ValueError, match="limit"):
        Throttle(limit=0, window=1.0, sink=collected.append)


def test_invalid_window_raises(collected):
    with pytest.raises(ValueError, match="window"):
        Throttle(limit=1, window=0, sink=collected.append)


def test_non_callable_sink_raises():
    with pytest.raises(TypeError, match="sink"):
        Throttle(limit=1, window=1.0, sink="not_callable")


# ---------------------------------------------------------------------------
# Core behaviour
# ---------------------------------------------------------------------------

def test_entries_within_limit_pass(collected, clock):
    t = Throttle(limit=3, window=1.0, sink=collected.append, clock=clock)
    for _ in range(3):
        t(_entry())
    assert len(collected) == 3
    assert t.dropped_count() == 0


def test_entries_beyond_limit_dropped(collected, clock):
    t = Throttle(limit=2, window=1.0, sink=collected.append, clock=clock)
    for _ in range(5):
        t(_entry())
    assert len(collected) == 2
    assert t.dropped_count() == 3


def test_window_rolls_over(collected, clock):
    t = Throttle(limit=2, window=1.0, sink=collected.append, clock=clock)
    t(_entry()); t(_entry())          # fills window
    t(_entry())                        # dropped
    clock.advance(1.01)                # window expires
    t(_entry()); t(_entry())          # allowed again
    assert len(collected) == 4
    assert t.dropped_count() == 1


def test_keys_are_tracked_independently(collected, clock):
    t = Throttle(limit=1, window=1.0, sink=collected.append, clock=clock)
    t(_entry(level="info"))
    t(_entry(level="info"))   # dropped for "info"
    t(_entry(level="error"))  # allowed for "error"
    assert len(collected) == 2
    assert t.dropped_count("info") == 1
    assert t.dropped_count("error") == 0


def test_custom_key_fn(collected, clock):
    t = Throttle(
        limit=1, window=1.0,
        sink=collected.append,
        key_fn=lambda e: e.get("tag"),
        clock=clock,
    )
    t(_entry(tag="gps"))
    t(_entry(tag="gps"))    # dropped
    t(_entry(tag="sensor")) # different key — allowed
    assert len(collected) == 2


def test_dropped_count_all_keys(collected, clock):
    t = Throttle(limit=1, window=1.0, sink=collected.append, clock=clock)
    t(_entry(level="info")); t(_entry(level="info"))   # 1 drop
    t(_entry(level="warn")); t(_entry(level="warn"))   # 1 drop
    assert t.dropped_count() == 2


def test_reset_clears_state(collected, clock):
    t = Throttle(limit=1, window=1.0, sink=collected.append, clock=clock)
    t(_entry()); t(_entry())  # 1 pass, 1 drop
    t.reset()
    assert t.dropped_count() == 0
    t(_entry())               # should pass again after reset
    assert len(collected) == 2
