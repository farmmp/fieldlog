"""Tests for fieldlog.pipeline_aggregator."""

from __future__ import annotations

import pytest
from fieldlog.pipeline_aggregator import AggregatorStage, aggregator_pipeline


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
# AggregatorStage construction
# ---------------------------------------------------------------------------

def test_non_callable_downstream_raises():
    with pytest.raises(TypeError):
        AggregatorStage(downstream="bad")


# ---------------------------------------------------------------------------
# Pass-through behaviour
# ---------------------------------------------------------------------------

def test_entries_forwarded_to_downstream():
    clock = _FakeClock()
    downstream = _collecting_sink()
    stage = AggregatorStage(downstream=downstream, interval=60.0, clock=clock)
    stage(_entry("info"))
    stage(_entry("warn"))
    assert len(downstream.collected) == 2


def test_summary_goes_to_separate_summary_sink():
    clock = _FakeClock()
    downstream = _collecting_sink()
    summaries = _collecting_sink()
    stage = AggregatorStage(
        downstream=downstream,
        summary_sink=summaries,
        interval=5.0,
        clock=clock,
    )
    stage(_entry("info"))
    clock.advance(6.0)
    stage(_entry("error"))  # triggers auto-flush
    # summary should NOT appear in downstream
    assert all(e["type"] != "aggregation_summary" for e in downstream.collected)
    assert len(summaries.collected) == 1
    assert summaries.collected[0]["type"] == "aggregation_summary"


def test_summary_defaults_to_downstream_when_no_summary_sink():
    clock = _FakeClock()
    downstream = _collecting_sink()
    stage = AggregatorStage(downstream=downstream, interval=5.0, clock=clock)
    stage(_entry())
    clock.advance(6.0)
    stage(_entry())  # triggers flush
    summaries = [e for e in downstream.collected if e.get("type") == "aggregation_summary"]
    assert len(summaries) == 1


# ---------------------------------------------------------------------------
# aggregator_pipeline factory
# ---------------------------------------------------------------------------

def test_aggregator_pipeline_returns_pipeline():
    from fieldlog.pipeline import Pipeline
    downstream = _collecting_sink()
    p = aggregator_pipeline(sink=downstream, interval=30.0)
    assert isinstance(p, Pipeline)


def test_aggregator_pipeline_processes_entries():
    clock = _FakeClock()
    downstream = _collecting_sink()
    summaries = _collecting_sink()
    p = aggregator_pipeline(
        sink=downstream,
        summary_sink=summaries,
        interval=10.0,
        clock=clock,
    )
    p(_entry("debug"))
    p(_entry("info"))
    assert len(downstream.collected) == 2
    clock.advance(11.0)
    p(_entry("warn"))  # flush triggered
    assert len(summaries.collected) == 1
    assert summaries.collected[0]["total"] == 2
