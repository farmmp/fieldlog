"""Tests for fieldlog.deadletter.DeadLetterQueue."""

from __future__ import annotations

import pytest

from fieldlog.deadletter import DeadLetterQueue


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeClock:
    def __init__(self, start: float = 1_000.0):
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


def _entry(**kwargs) -> dict:
    base = {"level": "error", "msg": "fail", "ts": 1}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_invalid_maxlen_raises():
    with pytest.raises(ValueError):
        DeadLetterQueue(maxlen=0)


def test_initial_empty():
    dlq = DeadLetterQueue()
    assert len(dlq) == 0


# ---------------------------------------------------------------------------
# Recording failures
# ---------------------------------------------------------------------------

def test_records_entry_with_timestamp():
    clock = _FakeClock(500.0)
    dlq = DeadLetterQueue(clock=clock)
    e = _entry()
    dlq(e)
    assert len(dlq) == 1
    stored = list(dlq)[0]
    assert stored["_dlq_ts"] == 500.0
    assert "msg" in stored


def test_records_error_string():
    dlq = DeadLetterQueue(clock=_FakeClock())
    dlq(_entry(), exc=RuntimeError("connection refused"))
    stored = list(dlq)[0]
    assert "connection refused" in stored["_dlq_error"]


def test_no_error_key_when_exc_is_none():
    dlq = DeadLetterQueue(clock=_FakeClock())
    dlq(_entry(), exc=None)
    stored = list(dlq)[0]
    assert "_dlq_error" not in stored


# ---------------------------------------------------------------------------
# Eviction / capacity
# ---------------------------------------------------------------------------

def test_oldest_evicted_when_full():
    dlq = DeadLetterQueue(maxlen=3, clock=_FakeClock())
    for i in range(5):
        dlq(_entry(msg=f"msg-{i}"))
    assert len(dlq) == 3
    msgs = [e["msg"] for e in dlq]
    assert msgs == ["msg-2", "msg-3", "msg-4"]


# ---------------------------------------------------------------------------
# Peek
# ---------------------------------------------------------------------------

def test_peek_returns_oldest_n():
    dlq = DeadLetterQueue(maxlen=10, clock=_FakeClock())
    for i in range(5):
        dlq(_entry(msg=f"msg-{i}"))
    peeked = dlq.peek(3)
    assert len(peeked) == 3
    assert peeked[0]["msg"] == "msg-0"
    assert len(dlq) == 5  # non-destructive


# ---------------------------------------------------------------------------
# Drain / replay
# ---------------------------------------------------------------------------

def test_drain_replays_all_entries():
    dlq = DeadLetterQueue(clock=_FakeClock())
    for i in range(4):
        dlq(_entry(msg=f"m{i}"))

    replayed = []
    count = dlq.drain(replayed.append)
    assert count == 4
    assert len(dlq) == 0
    assert len(replayed) == 4


def test_drain_strips_dlq_metadata():
    dlq = DeadLetterQueue(clock=_FakeClock())
    dlq(_entry(), exc=ValueError("oops"))

    replayed = []
    dlq.drain(replayed.append)
    assert "_dlq_ts" not in replayed[0]
    assert "_dlq_error" not in replayed[0]
    assert "msg" in replayed[0]


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------

def test_clear_empties_queue():
    dlq = DeadLetterQueue(clock=_FakeClock())
    dlq(_entry())
    dlq(_entry())
    dlq.clear()
    assert len(dlq) == 0
