"""Tests for fieldlog.splitter.Splitter."""
from __future__ import annotations

import pytest

from fieldlog.splitter import Splitter, SplitterError


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _entry(level: str = "info", tag: str = "app", msg: str = "hello") -> dict:
    return {"level": level, "tag": tag, "message": msg}


def _collecting_sink():
    collected = []

    def sink(entry):
        collected.append(entry)

    sink.collected = collected
    return sink


# ---------------------------------------------------------------------------
# construction errors
# ---------------------------------------------------------------------------

def test_non_callable_key_fn_raises():
    with pytest.raises(SplitterError, match="key_fn"):
        Splitter(key_fn="level", sinks={"info": lambda e: None})


def test_empty_sinks_raises():
    with pytest.raises(SplitterError, match="empty"):
        Splitter(key_fn=lambda e: e["level"], sinks={})


def test_non_callable_sink_value_raises():
    with pytest.raises(SplitterError, match="not callable"):
        Splitter(key_fn=lambda e: e["level"], sinks={"info": "not-a-sink"})


def test_non_callable_default_sink_raises():
    with pytest.raises(SplitterError, match="default_sink"):
        Splitter(
            key_fn=lambda e: e["level"],
            sinks={"info": lambda e: None},
            default_sink="bad",
        )


# ---------------------------------------------------------------------------
# routing behaviour
# ---------------------------------------------------------------------------

def test_entry_reaches_matching_sink():
    info_sink = _collecting_sink()
    warn_sink = _collecting_sink()
    sp = Splitter(
        key_fn=lambda e: e["level"],
        sinks={"info": info_sink, "warning": warn_sink},
    )
    entry = _entry(level="info")
    sp(entry)
    assert info_sink.collected == [entry]
    assert warn_sink.collected == []


def test_unmatched_key_uses_default_sink():
    default = _collecting_sink()
    sp = Splitter(
        key_fn=lambda e: e["level"],
        sinks={"info": lambda e: None},
        default_sink=default,
    )
    entry = _entry(level="debug")
    sp(entry)
    assert default.collected == [entry]


def test_unmatched_key_without_default_is_dropped():
    sp = Splitter(
        key_fn=lambda e: e["level"],
        sinks={"info": lambda e: None},
    )
    sp(_entry(level="debug"))
    assert sp.dropped_count == 1


def test_dropped_count_accumulates():
    sp = Splitter(
        key_fn=lambda e: e["level"],
        sinks={"info": lambda e: None},
    )
    for _ in range(5):
        sp(_entry(level="debug"))
    assert sp.dropped_count == 5


def test_reset_dropped_zeroes_counter():
    sp = Splitter(
        key_fn=lambda e: e["level"],
        sinks={"info": lambda e: None},
    )
    sp(_entry(level="debug"))
    sp.reset_dropped()
    assert sp.dropped_count == 0


def test_fanout_multiple_keys():
    sinks = {k: _collecting_sink() for k in ("info", "warning", "error")}
    sp = Splitter(key_fn=lambda e: e["level"], sinks=sinks)
    for level in ("info", "warning", "error", "info"):
        sp(_entry(level=level))
    assert len(sinks["info"].collected) == 2
    assert len(sinks["warning"].collected) == 1
    assert len(sinks["error"].collected) == 1


def test_add_sink_at_runtime():
    info_sink = _collecting_sink()
    debug_sink = _collecting_sink()
    sp = Splitter(key_fn=lambda e: e["level"], sinks={"info": info_sink})
    sp.add_sink("debug", debug_sink)
    sp(_entry(level="debug"))
    assert debug_sink.collected and sp.dropped_count == 0


def test_add_sink_non_callable_raises():
    sp = Splitter(key_fn=lambda e: e["level"], sinks={"info": lambda e: None})
    with pytest.raises(SplitterError, match="not callable"):
        sp.add_sink("debug", 42)


def test_keys_returns_registered_keys():
    sp = Splitter(
        key_fn=lambda e: e["level"],
        sinks={"info": lambda e: None, "error": lambda e: None},
    )
    assert set(sp.keys()) == {"info", "error"}


def test_key_fn_uses_arbitrary_field():
    tag_a = _collecting_sink()
    tag_b = _collecting_sink()
    sp = Splitter(
        key_fn=lambda e: e.get("tag", ""),
        sinks={"a": tag_a, "b": tag_b},
    )
    sp(_entry(tag="a"))
    sp(_entry(tag="b"))
    sp(_entry(tag="b"))
    assert len(tag_a.collected) == 1
    assert len(tag_b.collected) == 2
