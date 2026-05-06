"""Tests for fieldlog.buffer.LogBuffer."""

import pytest
from fieldlog.buffer import LogBuffer


def _entry(n: int):
    return {"seq": n, "msg": f"entry {n}"}


def test_push_and_len():
    buf = LogBuffer(maxsize=10)
    for i in range(5):
        buf.push(_entry(i))
    assert len(buf) == 5


def test_ring_eviction():
    buf = LogBuffer(maxsize=3)
    for i in range(5):
        buf.push(_entry(i))
    assert len(buf) == 3
    assert buf.dropped == 2
    seqs = [e["seq"] for e in buf]
    assert seqs == [2, 3, 4]


def test_flush_all():
    buf = LogBuffer(maxsize=10)
    for i in range(4):
        buf.push(_entry(i))
    flushed = buf.flush()
    assert len(flushed) == 4
    assert len(buf) == 0


def test_flush_partial():
    buf = LogBuffer(maxsize=10)
    for i in range(6):
        buf.push(_entry(i))
    flushed = buf.flush(3)
    assert len(flushed) == 3
    assert len(buf) == 3
    assert flushed[0]["seq"] == 0


def test_peek_does_not_remove():
    buf = LogBuffer(maxsize=10)
    for i in range(3):
        buf.push(_entry(i))
    peeked = buf.peek(2)
    assert len(peeked) == 2
    assert len(buf) == 3


def test_is_full():
    buf = LogBuffer(maxsize=2)
    buf.push(_entry(0))
    assert not buf.is_full
    buf.push(_entry(1))
    assert buf.is_full


def test_clear():
    buf = LogBuffer(maxsize=10)
    buf.push(_entry(0))
    buf.clear()
    assert len(buf) == 0


def test_invalid_maxsize():
    with pytest.raises(ValueError):
        LogBuffer(maxsize=0)
