"""Tests for fieldlog.tee.Tee."""
from __future__ import annotations

import pytest

from fieldlog.tee import Tee, TeeSinkError


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _entry(**kw) -> dict:
    return {"level": "info", "msg": "hello", **kw}


def _collecting_sink() -> tuple:
    """Return (sink_callable, collected_list)."""
    collected: list = []
    return collected.append, collected


# ---------------------------------------------------------------------------
# construction
# ---------------------------------------------------------------------------

def test_no_sinks_raises():
    with pytest.raises(ValueError, match="at least one sink"):
        Tee([])


def test_len_reflects_sink_count():
    sink_a, _ = _collecting_sink()
    sink_b, _ = _collecting_sink()
    tee = Tee([sink_a, sink_b])
    assert len(tee) == 2


# ---------------------------------------------------------------------------
# fan-out behaviour
# ---------------------------------------------------------------------------

def test_entry_reaches_all_sinks():
    sink_a, col_a = _collecting_sink()
    sink_b, col_b = _collecting_sink()
    tee = Tee([sink_a, sink_b])
    e = _entry()
    tee(e)
    assert col_a == [e]
    assert col_b == [e]


def test_multiple_entries_fan_out():
    sink_a, col_a = _collecting_sink()
    sink_b, col_b = _collecting_sink()
    tee = Tee([sink_a, sink_b])
    entries = [_entry(msg=f"m{i}") for i in range(5)]
    for e in entries:
        tee(e)
    assert col_a == entries
    assert col_b == entries


# ---------------------------------------------------------------------------
# error isolation
# ---------------------------------------------------------------------------

def test_failing_sink_does_not_block_others_by_default():
    """Healthy sinks still receive the entry even if an earlier one raises."""
    def bad_sink(entry):
        raise RuntimeError("boom")

    sink_good, col_good = _collecting_sink()
    tee = Tee([bad_sink, sink_good])  # bad first
    e = _entry()
    tee(e)  # must not raise
    assert col_good == [e]


def test_error_counts_incremented():
    call_count = {"n": 0}

    def flaky(entry):
        call_count["n"] += 1
        if call_count["n"] <= 2:
            raise IOError("disk full")

    sink_ok, _ = _collecting_sink()
    tee = Tee([flaky, sink_ok], names=["flaky", "ok"])
    for _ in range(4):
        tee(_entry())
    assert tee.error_counts["flaky"] == 2
    assert tee.error_counts["ok"] == 0


def test_raise_on_error_raises_tee_sink_error():
    def bad(entry):
        raise ValueError("nope")

    tee = Tee([bad], raise_on_error=True)
    with pytest.raises(TeeSinkError) as exc_info:
        tee(_entry())
    assert len(exc_info.value.failures) == 1
    assert exc_info.value.failures[0][0] == "sink_0"


def test_raise_on_error_still_calls_all_sinks_before_raising():
    def bad(entry):
        raise RuntimeError("err")

    sink_ok, col_ok = _collecting_sink()
    tee = Tee([bad, sink_ok], raise_on_error=True)
    with pytest.raises(TeeSinkError):
        tee(_entry())
    assert len(col_ok) == 1  # good sink was still called


# ---------------------------------------------------------------------------
# reset & names
# ---------------------------------------------------------------------------

def test_reset_error_counts_clears_counters():
    def bad(e):
        raise RuntimeError()

    tee = Tee([bad], names=["bad"])
    tee(_entry())
    assert tee.error_counts["bad"] == 1
    tee.reset_error_counts()
    assert tee.error_counts["bad"] == 0


def test_custom_names_appear_in_error_counts():
    sink_a, _ = _collecting_sink()
    sink_b, _ = _collecting_sink()
    tee = Tee([sink_a, sink_b], names=["alpha", "beta"])
    assert set(tee.error_counts.keys()) == {"alpha", "beta"}


def test_partial_names_fall_back_to_defaults():
    sink_a, _ = _collecting_sink()
    sink_b, _ = _collecting_sink()
    tee = Tee([sink_a, sink_b], names=["only_one"])
    keys = set(tee.error_counts.keys())
    assert "only_one" in keys
    assert "sink_1" in keys
