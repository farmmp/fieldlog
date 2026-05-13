"""Tests for fieldlog.sequencer.Sequencer."""

import threading
import pytest

from fieldlog.sequencer import Sequencer


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _entry(**kwargs):
    base = {"level": "info", "msg": "hello"}
    base.update(kwargs)
    return base


@pytest.fixture()
def collected():
    return []


@pytest.fixture()
def sink(collected):
    return collected.append


# ---------------------------------------------------------------------------
# construction
# ---------------------------------------------------------------------------

def test_non_callable_sink_raises():
    with pytest.raises(TypeError, match="callable"):
        Sequencer(sink=42)


def test_negative_start_raises():
    with pytest.raises(ValueError, match=">= 0"):
        Sequencer(sink=lambda e: None, start=-1)


def test_non_int_start_raises():
    with pytest.raises(TypeError, match="int"):
        Sequencer(sink=lambda e: None, start=1.5)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# basic stamping
# ---------------------------------------------------------------------------

def test_seq_starts_at_zero(sink, collected):
    seq = Sequencer(sink)
    seq(_entry())
    assert collected[0]["seq"] == 0


def test_seq_increments(sink, collected):
    seq = Sequencer(sink)
    for _ in range(5):
        seq(_entry())
    assert [e["seq"] for e in collected] == [0, 1, 2, 3, 4]


def test_custom_start(sink, collected):
    seq = Sequencer(sink, start=100)
    seq(_entry())
    assert collected[0]["seq"] == 100
    assert seq.current == 101


def test_custom_field_name(sink, collected):
    seq = Sequencer(sink, field="n")
    seq(_entry())
    assert "n" in collected[0]
    assert "seq" not in collected[0]


# ---------------------------------------------------------------------------
# overwrite behaviour
# ---------------------------------------------------------------------------

def test_existing_field_preserved_by_default(sink, collected):
    seq = Sequencer(sink)
    seq(_entry(seq=999))
    assert collected[0]["seq"] == 999
    assert seq.current == 0  # counter not advanced


def test_overwrite_replaces_existing(sink, collected):
    seq = Sequencer(sink, overwrite=True)
    seq(_entry(seq=999))
    assert collected[0]["seq"] == 0
    assert seq.current == 1


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------

def test_reset_to_zero(sink, collected):
    seq = Sequencer(sink)
    seq(_entry())
    seq(_entry())
    seq.reset()
    seq(_entry())
    assert collected[-1]["seq"] == 0


def test_reset_to_custom_value(sink):
    seq = Sequencer(sink)
    seq.reset(50)
    assert seq.current == 50


def test_reset_negative_raises(sink):
    seq = Sequencer(sink)
    with pytest.raises(ValueError):
        seq.reset(-1)


# ---------------------------------------------------------------------------
# thread safety
# ---------------------------------------------------------------------------

def test_thread_safety():
    results = []
    lock = threading.Lock()

    def sink(entry):
        with lock:
            results.append(entry["seq"])

    seq = Sequencer(sink)
    threads = [threading.Thread(target=seq, args=(_entry(),)) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == list(range(50))
