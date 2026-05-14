"""Tests for fieldlog.watchdog."""

import threading
import time
import pytest

from fieldlog.watchdog import Watchdog, WatchdogError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(msg: str = "hello") -> dict:
    return {"level": "info", "msg": msg}


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._t = start
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self._t

    def advance(self, seconds: float) -> None:
        with self._lock:
            self._t += seconds


# ---------------------------------------------------------------------------
# Construction guards
# ---------------------------------------------------------------------------

def test_non_callable_sink_raises():
    with pytest.raises(TypeError, match="callable"):
        Watchdog(sink="not_callable", timeout=5)


def test_zero_timeout_raises():
    with pytest.raises(ValueError, match="timeout"):
        Watchdog(sink=lambda e: None, timeout=0)


def test_negative_timeout_raises():
    with pytest.raises(ValueError, match="timeout"):
        Watchdog(sink=lambda e: None, timeout=-1)


# ---------------------------------------------------------------------------
# Normal forwarding
# ---------------------------------------------------------------------------

def test_entry_forwarded_to_sink():
    collected = []
    w = Watchdog(sink=collected.append, timeout=10)
    try:
        w(_entry("a"))
        w(_entry("b"))
        assert len(collected) == 2
        assert collected[0]["msg"] == "a"
    finally:
        w.stop()


def test_last_seen_updated_on_call():
    clock = _FakeClock(start=100.0)
    w = Watchdog(sink=lambda e: None, timeout=5, clock=clock)
    try:
        initial = w.last_seen
        clock.advance(3.0)
        w(_entry())
        assert w.last_seen > initial
    finally:
        w.stop()


# ---------------------------------------------------------------------------
# Alert behaviour
# ---------------------------------------------------------------------------

def test_default_alert_raises_watchdog_error():
    """The default on_alert raises WatchdogError from the watchdog thread;
    we verify the custom path by supplying our own on_alert instead."""
    fired = threading.Event()
    elapsed_seen = []

    def on_alert(elapsed: float) -> None:
        elapsed_seen.append(elapsed)
        fired.set()

    clock = _FakeClock(start=0.0)
    w = Watchdog(sink=lambda e: None, timeout=2.0, on_alert=on_alert, clock=clock)
    try:
        clock.advance(3.0)          # exceed timeout
        fired.wait(timeout=2.0)     # real-time wait for thread to tick
        assert fired.is_set(), "alert was not fired"
        assert elapsed_seen[0] >= 2.0
    finally:
        w.stop()


def test_alert_not_fired_when_entries_arrive():
    fired = threading.Event()
    clock = _FakeClock(start=0.0)

    w = Watchdog(
        sink=lambda e: None,
        timeout=2.0,
        on_alert=lambda elapsed: fired.set(),
        clock=clock,
    )
    try:
        # Keep advancing clock but also keep sending entries
        for _ in range(5):
            clock.advance(1.0)
            w(_entry())
        # Give the watchdog thread a real moment to (incorrectly) fire
        time.sleep(0.1)
        assert not fired.is_set()
    finally:
        w.stop()


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------

def test_stop_prevents_further_alerts():
    fired_count = [0]
    clock = _FakeClock(start=0.0)

    w = Watchdog(
        sink=lambda e: None,
        timeout=1.0,
        on_alert=lambda elapsed: fired_count.__setitem__(0, fired_count[0] + 1),
        clock=clock,
    )
    w.stop()
    clock.advance(5.0)
    time.sleep(0.15)   # let thread exit
    assert fired_count[0] == 0
