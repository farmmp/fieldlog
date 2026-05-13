"""Tests for fieldlog.aggregator."""

from __future__ import annotations

import pytest
from fieldlog.aggregator import Aggregator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


def _entry(level: str = "info", **kw):
    return {"level": level, "message": "test", **kw}


def _collecting_sink():
    collected = []
    def sink(entry):
        collected.append(entry)
    sink.collected = collected
    return sink


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_non_callable_sink_raises():
    with pytest.raises(TypeError):
        Aggregator(sink="not-callable")


def test_non_positive_interval_raises():
    sink = _collecting_sink()
    with pytest.raises(ValueError):
        Aggregator(sink=sink, interval=0)


def test_negative_interval_raises():
    sink = _collecting_sink()
    with pytest.raises(ValueError):
        Aggregator(sink=sink, interval=-5)


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------

def test_pending_increments_on_call():
    clock = _FakeClock()
    sink = _collecting_sink()
    agg = Aggregator(sink=sink, interval=10.0, clock=clock)
    assert agg.pending == 0
    agg(_entry("info"))
    agg(_entry("warn"))
    assert agg.pending == 2


def test_flush_resets_pending():
    clock = _FakeClock()
    sink = _collecting_sink()
    agg = Aggregator(sink=sink, interval=10.0, clock=clock)
    agg(_entry("info"))
    agg.flush()
    assert agg.pending == 0


def test_flush_emits_summary_with_counts():
    clock = _FakeClock()
    sink = _collecting_sink()
    agg = Aggregator(sink=sink, interval=10.0, clock=clock)
    agg(_entry("info"))
    agg(_entry("info"))
    agg(_entry("error"))
    agg.flush()
    assert len(sink.collected) == 1
    summary = sink.collected[0]
    assert summary["type"] == "aggregation_summary"
    assert summary["total"] == 3
    assert summary["counts"]["info"] == 2
    assert summary["counts"]["error"] == 1


def test_auto_flush_when_interval_exceeded():
    clock = _FakeClock()
    sink = _collecting_sink()
    agg = Aggregator(sink=sink, interval=5.0, clock=clock)
    agg(_entry("info"))
    clock.advance(6.0)  # exceed the interval
    agg(_entry("warn"))  # this call triggers auto-flush
    assert len(sink.collected) == 1
    assert sink.collected[0]["total"] == 1  # only the first entry
    assert agg.pending == 1  # new entry counted in new window


def test_summary_contains_window_times():
    clock = _FakeClock(start=100.0)
    sink = _collecting_sink()
    agg = Aggregator(sink=sink, interval=10.0, clock=clock)
    agg(_entry())
    clock.advance(10.0)
    agg.flush()
    summary = sink.collected[0]
    assert summary["window_start"] == pytest.approx(100.0)
    assert summary["window_end"] == pytest.approx(110.0)


def test_custom_key_field():
    clock = _FakeClock()
    sink = _collecting_sink()
    agg = Aggregator(sink=sink, interval=10.0, key_field="tag", clock=clock)
    agg({"tag": "gps", "message": "x"})
    agg({"tag": "gps", "message": "y"})
    agg({"tag": "sensor", "message": "z"})
    agg.flush()
    counts = sink.collected[0]["counts"]
    assert counts["gps"] == 2
    assert counts["sensor"] == 1


def test_missing_key_field_falls_back_to_unknown():
    clock = _FakeClock()
    sink = _collecting_sink()
    agg = Aggregator(sink=sink, interval=10.0, clock=clock)
    agg({"message": "no level here"})
    agg.flush()
    assert sink.collected[0]["counts"]["unknown"] == 1
