"""Tests for fieldlog.priority_queue."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from fieldlog.priority_queue import PriorityQueue, PriorityQueueError


def _entry(level: str, msg: str = "test") -> Dict[str, Any]:
    return {"level": level, "message": msg}


@pytest.fixture()
def collected() -> List[Dict[str, Any]]:
    return []


@pytest.fixture()
def sink(collected):
    def _sink(entry):
        collected.append(entry)
    return _sink


# ---------------------------------------------------------------------------
# Construction guards
# ---------------------------------------------------------------------------

def test_non_callable_sink_raises():
    with pytest.raises(PriorityQueueError, match="callable"):
        PriorityQueue(sink="not_callable")


def test_negative_max_size_raises():
    with pytest.raises(PriorityQueueError, match="max_size"):
        PriorityQueue(sink=lambda e: None, max_size=-1)


# ---------------------------------------------------------------------------
# Basic buffering
# ---------------------------------------------------------------------------

def test_pending_increases_on_call(sink, collected):
    q = PriorityQueue(sink)
    q(_entry("info"))
    q(_entry("debug"))
    assert q.pending == 2


def test_flush_returns_count(sink, collected):
    q = PriorityQueue(sink)
    for level in ("info", "debug", "error"):
        q(_entry(level))
    flushed = q.flush()
    assert flushed == 3


def test_flush_clears_buffer(sink, collected):
    q = PriorityQueue(sink)
    q(_entry("info"))
    q.flush()
    assert q.pending == 0


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------

def test_flush_orders_by_priority(sink, collected):
    q = PriorityQueue(sink)
    q(_entry("debug", "d"))
    q(_entry("info", "i"))
    q(_entry("critical", "c"))
    q(_entry("warning", "w"))
    q(_entry("error", "e"))
    q.flush()
    levels = [e["level"] for e in collected]
    assert levels == ["critical", "error", "warning", "info", "debug"]


def test_same_level_fifo_order(sink, collected):
    """Entries at the same level should come out in insertion order."""
    q = PriorityQueue(sink)
    for i in range(5):
        q({"level": "info", "seq": i})
    q.flush()
    assert [e["seq"] for e in collected] == list(range(5))


def test_unknown_level_treated_as_info(sink, collected):
    q = PriorityQueue(sink)
    q(_entry("verbose", "v"))  # unknown
    q(_entry("debug", "d"))
    q.flush()
    # unknown treated as info (priority 3) < debug (priority 4)
    assert collected[0]["level"] == "verbose"
    assert collected[1]["level"] == "debug"


# ---------------------------------------------------------------------------
# Eviction under max_size
# ---------------------------------------------------------------------------

def test_max_size_evicts_lowest_priority(sink, collected):
    q = PriorityQueue(sink, max_size=2)
    q(_entry("debug", "low"))
    q(_entry("info", "mid"))
    # This push should evict the debug entry
    q(_entry("error", "high"))
    assert q.pending == 2
    assert q.dropped_count == 1
    q.flush()
    levels = {e["level"] for e in collected}
    assert "debug" not in levels


def test_dropped_count_accumulates(sink):
    q = PriorityQueue(sink, max_size=1)
    q(_entry("info", "a"))
    q(_entry("info", "b"))  # evicts "a"
    q(_entry("info", "c"))  # evicts "b"
    assert q.dropped_count == 2
