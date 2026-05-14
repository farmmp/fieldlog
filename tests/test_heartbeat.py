"""Tests for fieldlog.heartbeat."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from fieldlog.heartbeat import Heartbeat, HeartbeatError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _entry(tag: str = "app", message: str = "hello") -> Dict[str, Any]:
    return {"level": "INFO", "tag": tag, "message": message}


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


def _collecting_sink() -> tuple[List[Dict[str, Any]], Any]:
    collected: List[Dict[str, Any]] = []

    def sink(entry: Dict[str, Any]) -> None:
        collected.append(entry)

    return collected, sink


# ---------------------------------------------------------------------------
# Construction guards
# ---------------------------------------------------------------------------


def test_non_callable_sink_raises():
    with pytest.raises(HeartbeatError, match="callable"):
        Heartbeat(sink="not_a_function", interval=5.0)  # type: ignore[arg-type]


def test_zero_interval_raises():
    _, sink = _collecting_sink()
    with pytest.raises(HeartbeatError, match="positive"):
        Heartbeat(sink=sink, interval=0)


def test_negative_interval_raises():
    _, sink = _collecting_sink()
    with pytest.raises(HeartbeatError, match="positive"):
        Heartbeat(sink=sink, interval=-1)


# ---------------------------------------------------------------------------
# Normal entry forwarding
# ---------------------------------------------------------------------------


def test_entry_forwarded_to_sink():
    collected, sink = _collecting_sink()
    clock = _FakeClock()
    hb = Heartbeat(sink=sink, interval=10.0, clock=clock)

    hb(_entry())
    assert len(collected) == 1
    assert collected[0]["message"] == "hello"


def test_real_entry_resets_idle_timer():
    collected, sink = _collecting_sink()
    clock = _FakeClock()
    hb = Heartbeat(sink=sink, interval=10.0, clock=clock)

    clock.advance(9.0)
    hb(_entry())          # resets timer
    clock.advance(9.0)    # only 9 s since last real entry
    fired = hb.tick()

    assert not fired
    assert hb.heartbeats_emitted == 0


# ---------------------------------------------------------------------------
# Heartbeat emission
# ---------------------------------------------------------------------------


def test_tick_emits_heartbeat_after_interval():
    collected, sink = _collecting_sink()
    clock = _FakeClock()
    hb = Heartbeat(sink=sink, interval=5.0, clock=clock)

    clock.advance(5.0)
    fired = hb.tick()

    assert fired
    assert hb.heartbeats_emitted == 1
    assert collected[-1]["tag"] == "heartbeat"
    assert collected[-1]["level"] == "DEBUG"


def test_tick_does_not_emit_before_interval():
    collected, sink = _collecting_sink()
    clock = _FakeClock()
    hb = Heartbeat(sink=sink, interval=5.0, clock=clock)

    clock.advance(4.9)
    fired = hb.tick()

    assert not fired
    assert hb.heartbeats_emitted == 0
    assert collected == []


def test_multiple_ticks_accumulate():
    collected, sink = _collecting_sink()
    clock = _FakeClock()
    hb = Heartbeat(sink=sink, interval=5.0, clock=clock)

    for _ in range(3):
        clock.advance(5.0)
        hb.tick()

    assert hb.heartbeats_emitted == 3
    indices = [e["heartbeat_index"] for e in collected]
    assert indices == [1, 2, 3]


def test_heartbeat_index_increments_sequentially():
    collected, sink = _collecting_sink()
    clock = _FakeClock()
    hb = Heartbeat(sink=sink, interval=1.0, clock=clock)

    clock.advance(1.0)
    hb.tick()
    clock.advance(1.0)
    hb.tick()

    assert collected[0]["heartbeat_index"] == 1
    assert collected[1]["heartbeat_index"] == 2


def test_custom_tag_appears_in_heartbeat():
    collected, sink = _collecting_sink()
    clock = _FakeClock()
    hb = Heartbeat(sink=sink, interval=1.0, tag="alive", clock=clock)

    clock.advance(1.0)
    hb.tick()

    assert collected[0]["tag"] == "alive"


# ---------------------------------------------------------------------------
# idle_seconds property
# ---------------------------------------------------------------------------


def test_idle_seconds_reflects_elapsed_time():
    _, sink = _collecting_sink()
    clock = _FakeClock(start=100.0)
    hb = Heartbeat(sink=sink, interval=10.0, clock=clock)

    clock.advance(7.0)
    assert abs(hb.idle_seconds - 7.0) < 1e-9


def test_idle_seconds_resets_after_real_entry():
    _, sink = _collecting_sink()
    clock = _FakeClock()
    hb = Heartbeat(sink=sink, interval=10.0, clock=clock)

    clock.advance(8.0)
    hb(_entry())          # resets
    assert hb.idle_seconds < 1e-9
