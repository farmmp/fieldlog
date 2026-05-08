"""Tests for fieldlog.instrumented_sink.InstrumentedSink."""
from __future__ import annotations

from typing import Any, Dict, List

import pytest

from fieldlog.metrics import Metrics
from fieldlog.instrumented_sink import InstrumentedSink


def _entry(**kw) -> Dict[str, Any]:
    base = {"level": "info", "msg": "hello", "ts": "2024-01-01T00:00:00"}
    base.update(kw)
    return base


@pytest.fixture()
def metrics() -> Metrics:
    return Metrics()


@pytest.fixture()
def collected() -> List[Dict[str, Any]]:
    return []


@pytest.fixture()
def sink(collected, metrics):
    return InstrumentedSink(lambda e: collected.append(e), metrics, name="test")


def test_non_callable_raises(metrics):
    with pytest.raises(TypeError):
        InstrumentedSink("not_callable", metrics, name="bad")


def test_entry_forwarded_to_inner_sink(sink, collected):
    e = _entry()
    sink(e)
    assert collected == [e]


def test_accepted_counter_increments(sink, metrics):
    sink(_entry())
    sink(_entry())
    assert sink.accepted() == 2


def test_error_counter_increments_on_exception(metrics):
    def bad_sink(e):
        raise RuntimeError("disk full")

    s = InstrumentedSink(bad_sink, metrics, name="bad")
    with pytest.raises(RuntimeError):
        s(_entry())
    assert s.errors() == 1
    assert s.accepted() == 0


def test_exception_is_re_raised(metrics):
    def bad_sink(e):
        raise ValueError("oops")

    s = InstrumentedSink(bad_sink, metrics, name="err")
    with pytest.raises(ValueError, match="oops"):
        s(_entry())


def test_metrics_keys_are_namespaced(metrics):
    sink = InstrumentedSink(lambda e: None, metrics, name="primary")
    sink(_entry())
    snap = metrics.snapshot()
    assert "sink.primary.accepted" in snap["counters"]


def test_multiple_sinks_isolated(metrics):
    s1 = InstrumentedSink(lambda e: None, metrics, name="s1")
    s2 = InstrumentedSink(lambda e: None, metrics, name="s2")
    s1(_entry())
    s1(_entry())
    s2(_entry())
    assert s1.accepted() == 2
    assert s2.accepted() == 1


def test_name_property(metrics):
    s = InstrumentedSink(lambda e: None, metrics, name="myname")
    assert s.name == "myname"
