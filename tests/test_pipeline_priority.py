"""Tests for fieldlog.pipeline_priority."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from fieldlog.pipeline_priority import PriorityStage


def _entry(level: str, msg: str = "x") -> Dict[str, Any]:
    return {"level": level, "message": msg}


@pytest.fixture()
def collected() -> List[Dict[str, Any]]:
    return []


@pytest.fixture()
def stage(collected):
    s = PriorityStage(max_size=0)
    s.bind(collected.append)
    return s


# ---------------------------------------------------------------------------
# Bind guard
# ---------------------------------------------------------------------------

def test_call_before_bind_raises():
    s = PriorityStage()
    with pytest.raises(RuntimeError, match="bound"):
        s(_entry("info"))


# ---------------------------------------------------------------------------
# Buffering behaviour
# ---------------------------------------------------------------------------

def test_entries_not_forwarded_until_flush(stage, collected):
    stage(_entry("info"))
    stage(_entry("error"))
    assert collected == []
    assert stage.pending == 2


def test_flush_forwards_in_priority_order(stage, collected):
    stage(_entry("debug"))
    stage(_entry("critical"))
    stage(_entry("warning"))
    stage.flush()
    assert [e["level"] for e in collected] == ["critical", "warning", "debug"]


def test_flush_returns_forwarded_count(stage, collected):
    stage(_entry("info"))
    stage(_entry("info"))
    assert stage.flush() == 2


def test_pending_is_zero_after_flush(stage):
    stage(_entry("info"))
    stage.flush()
    assert stage.pending == 0


# ---------------------------------------------------------------------------
# max_size / dropped_count
# ---------------------------------------------------------------------------

def test_dropped_count_exposed(collected):
    s = PriorityStage(max_size=1)
    s.bind(collected.append)
    s(_entry("info", "a"))
    s(_entry("info", "b"))  # triggers eviction
    assert s.dropped_count == 1


def test_flush_on_unbound_stage_returns_zero():
    s = PriorityStage()
    assert s.flush() == 0


def test_pending_on_unbound_stage_returns_zero():
    s = PriorityStage()
    assert s.pending == 0


# ---------------------------------------------------------------------------
# Multiple flushes
# ---------------------------------------------------------------------------

def test_second_flush_is_empty(stage, collected):
    stage(_entry("error"))
    stage.flush()
    stage.flush()  # should not raise, should forward nothing extra
    assert len(collected) == 1
