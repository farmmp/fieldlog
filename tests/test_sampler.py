"""Tests for fieldlog.sampler."""

import pytest
from fieldlog.sampler import Sampler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(level: str = "info", msg: str = "hello", uid: str = "u1"):
    return {"level": level, "msg": msg, "uid": uid}


def _collecting_sink():
    collected = []
    def sink(entry):
        collected.append(entry)
    sink.collected = collected
    return sink


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_invalid_rate_raises():
    sink = _collecting_sink()
    with pytest.raises(ValueError):
        Sampler(sink, rate=1.5)


def test_rate_zero_drops_all():
    sink = _collecting_sink()
    s = Sampler(sink, rate=0.0)
    for _ in range(20):
        s(_entry())
    assert len(sink.collected) == 0


def test_rate_one_passes_all():
    sink = _collecting_sink()
    s = Sampler(sink, rate=1.0)
    for _ in range(20):
        s(_entry())
    assert len(sink.collected) == 20


# ---------------------------------------------------------------------------
# Counter-based sampling
# ---------------------------------------------------------------------------

def test_counter_half_rate():
    sink = _collecting_sink()
    s = Sampler(sink, rate=0.5)  # every 2nd entry
    for _ in range(10):
        s(_entry())
    assert len(sink.collected) == 5


def test_counter_tenth_rate():
    sink = _collecting_sink()
    s = Sampler(sink, rate=0.1)  # every 10th entry
    for _ in range(100):
        s(_entry())
    assert len(sink.collected) == 10


# ---------------------------------------------------------------------------
# Deterministic (key-field) sampling
# ---------------------------------------------------------------------------

def test_deterministic_same_key_always_same_decision():
    sink = _collecting_sink()
    s = Sampler(sink, rate=0.5, key_field="uid")
    entry = _entry(uid="stable-key")
    results = set()
    for _ in range(10):
        before = len(sink.collected)
        s(entry)
        results.add(len(sink.collected) > before)
    # All calls with the same key must produce the same outcome
    assert len(results) == 1


def test_deterministic_spread_across_keys():
    sink = _collecting_sink()
    s = Sampler(sink, rate=0.5, key_field="uid")
    for i in range(200):
        s(_entry(uid=str(i)))
    # With 200 distinct keys at 50% we expect roughly 100 ± 20
    assert 80 <= len(sink.collected) <= 120


def test_rate_property():
    sink = _collecting_sink()
    s = Sampler(sink, rate=0.25)
    assert s.rate == 0.25
