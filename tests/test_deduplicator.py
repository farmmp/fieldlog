"""Tests for fieldlog.deduplicator."""

import pytest
from fieldlog.deduplicator import Deduplicator, _entry_fingerprint


def _entry(level="info", message="hello", tag="app", **kwargs):
    e = {"level": level, "message": message, "tag": tag}
    e.update(kwargs)
    return e


class _FakeClock:
    def __init__(self, start: float = 0.0):
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


def _collecting_sink():
    collected = []

    def sink(entry):
        collected.append(entry)

    sink.collected = collected
    return sink


def test_first_entry_always_forwarded():
    sink = _collecting_sink()
    d = Deduplicator(sink, window_seconds=10)
    d(_entry())
    assert len(sink.collected) == 1
    assert d.suppressed_count == 0


def test_duplicate_within_window_suppressed():
    sink = _collecting_sink()
    clock = _FakeClock()
    d = Deduplicator(sink, window_seconds=30, clock=clock)
    d(_entry())
    clock.advance(5)
    d(_entry())
    clock.advance(5)
    d(_entry())
    assert len(sink.collected) == 1
    assert d.suppressed_count == 2


def test_entry_allowed_after_window_expires():
    sink = _collecting_sink()
    clock = _FakeClock()
    d = Deduplicator(sink, window_seconds=10, clock=clock)
    d(_entry())
    clock.advance(10)  # exactly at boundary -> new window
    d(_entry())
    assert len(sink.collected) == 2
    assert d.suppressed_count == 0


def test_different_messages_not_deduplicated():
    sink = _collecting_sink()
    clock = _FakeClock()
    d = Deduplicator(sink, window_seconds=60, clock=clock)
    d(_entry(message="msg-a"))
    d(_entry(message="msg-b"))
    assert len(sink.collected) == 2


def test_different_levels_not_deduplicated():
    sink = _collecting_sink()
    d = Deduplicator(sink, window_seconds=60)
    d(_entry(level="info"))
    d(_entry(level="error"))
    assert len(sink.collected) == 2


def test_reset_clears_state():
    sink = _collecting_sink()
    clock = _FakeClock()
    d = Deduplicator(sink, window_seconds=60, clock=clock)
    d(_entry())
    d(_entry())  # suppressed
    assert d.suppressed_count == 1
    d.reset()
    assert d.suppressed_count == 0
    d(_entry())  # should pass through after reset
    assert len(sink.collected) == 2


def test_invalid_window_raises():
    with pytest.raises(ValueError):
        Deduplicator(lambda e: None, window_seconds=0)
    with pytest.raises(ValueError):
        Deduplicator(lambda e: None, window_seconds=-5)


def test_fingerprint_ignores_extra_fields():
    fp1 = _entry_fingerprint(_entry(extra="x"))
    fp2 = _entry_fingerprint(_entry(extra="y"))
    assert fp1 == fp2
