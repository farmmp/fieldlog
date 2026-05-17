"""Tests for fieldlog.replay and fieldlog.pipeline_replay."""

from __future__ import annotations

import pytest

from fieldlog.replay import Replay, ReplayError, ReplayStats
from fieldlog.pipeline_replay import ReplayStage, replay_pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(level: str = "info", msg: str = "hello") -> dict:
    return {"level": level, "message": msg, "timestamp": "2024-01-01T00:00:00Z"}


def _collecting_sink():
    collected = []

    def sink(entry: dict) -> None:
        collected.append(entry)

    sink.collected = collected
    return sink


# ---------------------------------------------------------------------------
# Replay – construction guards
# ---------------------------------------------------------------------------

def test_non_callable_sink_raises():
    with pytest.raises(ReplayError, match="callable"):
        Replay(sink="not_a_function")


def test_negative_delay_raises():
    with pytest.raises(ReplayError, match="delay"):
        Replay(sink=lambda e: None, delay=-1)


# ---------------------------------------------------------------------------
# Replay – basic behaviour
# ---------------------------------------------------------------------------

def test_all_entries_forwarded():
    sink = _collecting_sink()
    entries = [_entry("info"), _entry("error"), _entry("debug")]
    r = Replay(sink)
    stats = r.run(entries)

    assert len(sink.collected) == 3
    assert stats.replayed == 3
    assert stats.skipped == 0


def test_predicate_filters_entries():
    sink = _collecting_sink()
    entries = [_entry("info"), _entry("error"), _entry("info")]
    r = Replay(sink, predicate=lambda e: e["level"] == "error")
    stats = r.run(entries)

    assert len(sink.collected) == 1
    assert sink.collected[0]["level"] == "error"
    assert stats.replayed == 1
    assert stats.skipped == 2


def test_transform_applied_before_forwarding():
    sink = _collecting_sink()
    entries = [_entry("info", "original")]
    r = Replay(sink, transform=lambda e: {**e, "message": "transformed"})
    r.run(entries)

    assert sink.collected[0]["message"] == "transformed"


def test_empty_entries_returns_zero_stats():
    sink = _collecting_sink()
    r = Replay(sink)
    stats = r.run([])

    assert stats.replayed == 0
    assert stats.skipped == 0
    assert len(sink.collected) == 0


def test_replayed_and_skipped_properties_updated():
    sink = _collecting_sink()
    entries = [_entry("debug"), _entry("error")]
    r = Replay(sink, predicate=lambda e: e["level"] == "error")
    r.run(entries)

    assert r.replayed == 1
    assert r.skipped == 1


def test_run_resets_counters_on_second_call():
    sink = _collecting_sink()
    entries = [_entry()]
    r = Replay(sink)
    r.run(entries)
    r.run([])  # second call with no entries

    assert r.replayed == 0
    assert r.skipped == 0


# ---------------------------------------------------------------------------
# ReplayStage
# ---------------------------------------------------------------------------

def test_run_before_bind_raises():
    stage = ReplayStage()
    with pytest.raises(RuntimeError, match="bind"):
        stage.run([])


def test_stage_replayed_before_bind_is_zero():
    stage = ReplayStage()
    assert stage.replayed == 0
    assert stage.skipped == 0


def test_stage_forwards_entries():
    sink = _collecting_sink()
    stage = ReplayStage()
    stage.bind(sink)
    stats = stage.run([_entry(), _entry()])

    assert len(sink.collected) == 2
    assert stats.replayed == 2


def test_stage_predicate_works():
    sink = _collecting_sink()
    stage = ReplayStage(predicate=lambda e: e["level"] == "debug")
    stage.bind(sink)
    stage.run([_entry("info"), _entry("debug")])

    assert len(sink.collected) == 1
    assert stage.replayed == 1
    assert stage.skipped == 1


# ---------------------------------------------------------------------------
# replay_pipeline convenience function
# ---------------------------------------------------------------------------

def test_replay_pipeline_convenience():
    sink = _collecting_sink()
    entries = [_entry("info"), _entry("error")]
    stats = replay_pipeline(entries, sink, predicate=lambda e: e["level"] == "error")

    assert len(sink.collected) == 1
    assert stats.replayed == 1
    assert stats.skipped == 1


def test_replay_pipeline_transform():
    sink = _collecting_sink()
    stats = replay_pipeline(
        [_entry()],
        sink,
        transform=lambda e: {**e, "replayed": True},
    )
    assert sink.collected[0]["replayed"] is True
    assert stats.replayed == 1
