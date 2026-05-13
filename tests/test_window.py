"""Tests for fieldlog.window.Window."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from fieldlog.window import Window


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(msg: str = "hello", level: str = "INFO") -> Dict[str, Any]:
    return {"message": msg, "level": level}


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


def _collecting_sink() -> tuple[List[Dict[str, Any]], Any]:
    received: List[Dict[str, Any]] = []

    def sink(summary: Dict[str, Any]) -> None:
        received.append(summary)

    return received, sink


# ---------------------------------------------------------------------------
# Construction guards
# ---------------------------------------------------------------------------

def test_non_callable_sink_raises():
    with pytest.raises(TypeError):
        Window(sink="not_callable", duration=10)  # type: ignore[arg-type]


def test_zero_duration_raises():
    received, sink = _collecting_sink()
    with pytest.raises(ValueError):
        Window(sink=sink, duration=0)


def test_negative_duration_raises():
    received, sink = _collecting_sink()
    with pytest.raises(ValueError):
        Window(sink=sink, duration=-5)


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

def test_pending_starts_at_zero():
    _, sink = _collecting_sink()
    w = Window(sink=sink, duration=10, clock=_FakeClock())
    assert w.pending() == 0


def test_entries_accumulate_within_window():
    clock = _FakeClock()
    _, sink = _collecting_sink()
    w = Window(sink=sink, duration=10, clock=clock)
    w(_entry("a"))
    w(_entry("b"))
    assert w.pending() == 2


def test_window_closes_when_duration_exceeded():
    clock = _FakeClock()
    received, sink = _collecting_sink()
    w = Window(sink=sink, duration=10, clock=clock)
    w(_entry("a"))
    w(_entry("b"))
    clock.advance(11)          # cross the boundary
    w(_entry("c"))             # this call triggers flush then adds "c"
    assert len(received) == 1
    summary = received[0]
    assert summary["count"] == 2
    assert len(summary["entries"]) == 2
    assert w.pending() == 1   # "c" is now in the new window


def test_summary_contains_timing_fields():
    clock = _FakeClock(start=100.0)
    received, sink = _collecting_sink()
    w = Window(sink=sink, duration=10, clock=clock)
    w(_entry())
    clock.advance(15)
    w(_entry())  # triggers flush
    summary = received[0]
    assert summary["window_start"] == pytest.approx(100.0)
    assert summary["window_end"] == pytest.approx(115.0)


def test_force_flush_sends_summary():
    clock = _FakeClock()
    received, sink = _collecting_sink()
    w = Window(sink=sink, duration=60, clock=clock)
    w(_entry("x"))
    w(_entry("y"))
    w.flush()
    assert len(received) == 1
    assert received[0]["count"] == 2
    assert w.pending() == 0


def test_multiple_windows_accumulate_independently():
    clock = _FakeClock()
    received, sink = _collecting_sink()
    w = Window(sink=sink, duration=5, clock=clock)
    for _ in range(3):
        w(_entry())
    clock.advance(6)
    for _ in range(2):
        w(_entry())  # first call flushes window-1, then adds entry
    w.flush()        # close window-2
    assert len(received) == 2
    assert received[0]["count"] == 3
    assert received[1]["count"] == 2


def test_flush_empty_window_sends_zero_count():
    clock = _FakeClock()
    received, sink = _collecting_sink()
    w = Window(sink=sink, duration=30, clock=clock)
    w.flush()
    assert len(received) == 1
    assert received[0]["count"] == 0
    assert received[0]["entries"] == []
