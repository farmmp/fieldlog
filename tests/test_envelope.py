"""Tests for fieldlog.envelope and fieldlog.envelope_sink."""

import time

import pytest

from fieldlog.envelope import Envelope, wrap
from fieldlog.envelope_sink import EnvelopeSink


def _entry(**kwargs):
    base = {"level": "info", "msg": "hello"}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Envelope
# ---------------------------------------------------------------------------

def test_wrap_creates_envelope():
    e = wrap(_entry(), origin="device-1", region="eu")
    assert isinstance(e, Envelope)
    assert e.origin == "device-1"
    assert e.tags["region"] == "eu"
    assert e.attempt == 0


def test_envelope_id_is_unique():
    e1 = wrap(_entry())
    e2 = wrap(_entry())
    assert e1.envelope_id != e2.envelope_id


def test_next_attempt_increments():
    e = wrap(_entry())
    e2 = e.next_attempt()
    assert e2.attempt == 1
    assert e2.envelope_id == e.envelope_id
    assert e2.entry is not e.entry  # same content, different dict


def test_next_attempt_chained():
    e = wrap(_entry())
    assert e.next_attempt().next_attempt().attempt == 2


def test_age_grows_over_time():
    e = wrap(_entry())
    age1 = e.age()
    time.sleep(0.01)
    age2 = e.age()
    assert age2 > age1


def test_age_with_fake_clock():
    now = [100.0]
    e = Envelope(entry=_entry(), created_at=90.0)
    assert e.age(clock=lambda: now[0]) == pytest.approx(10.0)


def test_roundtrip_dict():
    e = wrap(_entry(msg="roundtrip"), origin="dev", zone="a")
    restored = Envelope.from_dict(e.to_dict())
    assert restored.envelope_id == e.envelope_id
    assert restored.origin == e.origin
    assert restored.tags == e.tags
    assert restored.entry == e.entry
    assert restored.attempt == e.attempt


# ---------------------------------------------------------------------------
# EnvelopeSink
# ---------------------------------------------------------------------------

def test_non_callable_sink_raises():
    with pytest.raises(TypeError):
        EnvelopeSink("not_callable")


def test_forwards_entry_to_sink():
    received = []
    sink = EnvelopeSink(received.append)
    e = wrap(_entry(msg="test"))
    sink(e)
    assert received[0]["msg"] == "test"
    assert sink.forwarded == 1


def test_non_envelope_raises_and_counts():
    sink = EnvelopeSink(lambda x: None)
    with pytest.raises(TypeError):
        sink({"msg": "bare dict"})
    assert sink.rejected == 1


def test_inject_metadata_adds_fields():
    received = []
    sink = EnvelopeSink(received.append, inject_metadata=True)
    e = wrap(_entry(), origin="edge-7", region="us")
    sink(e)
    rec = received[0]
    assert "_env_id" in rec
    assert rec["_env_attempt"] == 0
    assert rec["_env_origin"] == "edge-7"
    assert rec["_env_tag_region"] == "us"


def test_inject_metadata_custom_prefix():
    received = []
    sink = EnvelopeSink(received.append, inject_metadata=True, metadata_prefix="meta.")
    e = wrap(_entry(), origin="x")
    sink(e)
    assert "meta.id" in received[0]
    assert received[0]["meta.origin"] == "x"


def test_no_metadata_injection_by_default():
    received = []
    sink = EnvelopeSink(received.append)
    e = wrap(_entry(), origin="y")
    sink(e)
    assert "_env_origin" not in received[0]


def test_forwarded_count_accumulates():
    sink = EnvelopeSink(lambda x: None)
    for _ in range(5):
        sink(wrap(_entry()))
    assert sink.forwarded == 5
