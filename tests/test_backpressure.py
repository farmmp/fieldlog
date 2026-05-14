"""Tests for fieldlog.backpressure."""

from __future__ import annotations

import threading
import time
from typing import List

import pytest

from fieldlog.backpressure import Backpressure, BackpressureError


def _entry(msg: str = "hello") -> dict:
    return {"level": "info", "message": msg}


def _collecting_sink() -> tuple[List[dict], callable]:
    collected: List[dict] = []

    def sink(entry: dict) -> None:
        collected.append(entry)

    return collected, sink


# ---------------------------------------------------------------------------
# Construction validation
# ---------------------------------------------------------------------------

def test_non_callable_sink_raises():
    with pytest.raises(BackpressureError, match="callable"):
        Backpressure("not-a-sink")


def test_max_pending_zero_raises():
    _, sink = _collecting_sink()
    with pytest.raises(BackpressureError, match="max_pending"):
        Backpressure(sink, max_pending=0)


def test_invalid_policy_raises():
    _, sink = _collecting_sink()
    with pytest.raises(BackpressureError, match="policy"):
        Backpressure(sink, policy="reject")


# ---------------------------------------------------------------------------
# Drop policy
# ---------------------------------------------------------------------------

def test_entries_forwarded_to_sink():
    collected, sink = _collecting_sink()
    bp = Backpressure(sink, max_pending=10, policy="drop")
    bp(_entry("a"))
    bp(_entry("b"))
    assert len(collected) == 2
    assert bp.dropped_count == 0


def test_drop_policy_drops_when_full():
    """Saturate the semaphore by never releasing, then confirm drops."""
    barrier = threading.Event()
    results: List[dict] = []

    def slow_sink(entry):
        results.append(entry)
        barrier.wait()  # hold the semaphore slot

    bp = Backpressure(slow_sink, max_pending=1, policy="drop")

    # First entry acquires the slot and blocks inside slow_sink (in a thread)
    t = threading.Thread(target=bp, args=(_entry("first"),))
    t.start()
    time.sleep(0.05)  # let the thread acquire the semaphore

    # Second entry should be dropped
    bp(_entry("second"))
    assert bp.dropped_count == 1

    barrier.set()
    t.join(timeout=2)


# ---------------------------------------------------------------------------
# Block policy
# ---------------------------------------------------------------------------

def test_block_policy_timeout_raises():
    barrier = threading.Event()

    def slow_sink(entry):
        barrier.wait()

    bp = Backpressure(slow_sink, max_pending=1, policy="block", timeout=0.1)

    t = threading.Thread(target=bp, args=(_entry("first"),))
    t.start()
    time.sleep(0.05)

    with pytest.raises(BackpressureError, match="timeout"):
        bp(_entry("overflow"))

    barrier.set()
    t.join(timeout=2)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_reset_stats_clears_dropped():
    barrier = threading.Event()

    def slow_sink(entry):
        barrier.wait()

    bp = Backpressure(slow_sink, max_pending=1, policy="drop")
    t = threading.Thread(target=bp, args=(_entry(),))
    t.start()
    time.sleep(0.05)
    bp(_entry())  # dropped
    assert bp.dropped_count == 1
    bp.reset_stats()
    assert bp.dropped_count == 0
    barrier.set()
    t.join(timeout=2)


def test_properties_reflect_config():
    _, sink = _collecting_sink()
    bp = Backpressure(sink, max_pending=42, policy="drop")
    assert bp.max_pending == 42
    assert bp.policy == "drop"
