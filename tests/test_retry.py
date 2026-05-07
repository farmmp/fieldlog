"""Tests for fieldlog.retry.RetrySink."""

from __future__ import annotations

import pytest

from fieldlog.retry import RetrySink, RetryError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(**kwargs) -> dict:
    base = {"level": "error", "msg": "boom", "ts": 0}
    base.update(kwargs)
    return base


class _FakeSleep:
    def __init__(self):
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_invalid_max_attempts_raises():
    with pytest.raises(ValueError, match="max_attempts"):
        RetrySink(sink=lambda e: None, max_attempts=0)


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------

def test_success_on_first_attempt():
    received = []
    sink = RetrySink(lambda e: received.append(e))
    sink(_entry())
    assert len(received) == 1
    assert sink.total_attempts == 1
    assert sink.total_failures == 0


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------

def test_retries_until_success():
    calls = []
    sleeper = _FakeSleep()

    def flaky(entry):
        calls.append(entry)
        if len(calls) < 3:
            raise OSError("network unavailable")

    sink = RetrySink(flaky, max_attempts=5, backoff_base=1.0, sleep=sleeper)
    sink(_entry())

    assert len(calls) == 3
    assert sink.total_attempts == 3
    assert sink.total_failures == 0
    assert sleeper.calls == [1.0, 2.0]


def test_backoff_capped_at_max_delay():
    sleeper = _FakeSleep()

    def always_fail(entry):
        raise OSError("fail")

    sink = RetrySink(
        always_fail,
        max_attempts=4,
        backoff_base=10.0,
        backoff_factor=3.0,
        max_delay=15.0,
        on_failure=lambda e, ex: None,
        sleep=sleeper,
    )
    sink(_entry())
    assert all(d <= 15.0 for d in sleeper.calls)


# ---------------------------------------------------------------------------
# Exhausted retries
# ---------------------------------------------------------------------------

def test_raises_retry_error_when_no_on_failure():
    sink = RetrySink(
        lambda e: (_ for _ in ()).throw(RuntimeError("dead")),
        max_attempts=2,
        sleep=_FakeSleep(),
    )
    with pytest.raises(RetryError):
        sink(_entry())
    assert sink.total_failures == 1


def test_on_failure_callback_suppresses_exception():
    failures = []

    def cb(entry, exc):
        failures.append((entry, exc))

    sink = RetrySink(
        lambda e: (_ for _ in ()).throw(ValueError("bad")),
        max_attempts=2,
        on_failure=cb,
        sleep=_FakeSleep(),
    )
    e = _entry()
    sink(e)  # must not raise
    assert len(failures) == 1
    assert failures[0][0] is e
    assert isinstance(failures[0][1], ValueError)


# ---------------------------------------------------------------------------
# Stats / reset
# ---------------------------------------------------------------------------

def test_reset_stats():
    sink = RetrySink(lambda e: None)
    sink(_entry())
    sink._total_failures = 2  # simulate failures
    sink.reset_stats()
    assert sink.total_attempts == 0
    assert sink.total_failures == 0


def test_cumulative_attempts_across_entries():
    calls = []

    def flaky(entry):
        calls.append(1)
        if len(calls) % 2 == 1:
            raise OSError()

    sink = RetrySink(flaky, max_attempts=3, sleep=_FakeSleep())
    sink(_entry())
    sink(_entry())
    # entry1: 2 attempts (fail, succeed), entry2: 1 attempt (succeed)
    assert sink.total_attempts == 3
