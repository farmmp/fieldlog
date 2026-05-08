"""Tests for fieldlog.metrics.Metrics."""
import threading
import pytest

from fieldlog.metrics import Metrics


@pytest.fixture()
def m() -> Metrics:
    return Metrics()


def test_counter_starts_at_zero(m):
    assert m.counter("events") == 0


def test_increment_default_amount(m):
    m.increment("events")
    assert m.counter("events") == 1


def test_increment_custom_amount(m):
    m.increment("bytes", 512)
    assert m.counter("bytes") == 512


def test_increment_accumulates(m):
    for _ in range(5):
        m.increment("hits")
    assert m.counter("hits") == 5


def test_increment_negative_raises(m):
    with pytest.raises(ValueError):
        m.increment("x", -1)


def test_gauge_unset_returns_none(m):
    assert m.gauge("queue_depth") is None


def test_set_and_read_gauge(m):
    m.set_gauge("queue_depth", 42.0)
    assert m.gauge("queue_depth") == 42.0


def test_gauge_overwrite(m):
    m.set_gauge("load", 0.5)
    m.set_gauge("load", 0.9)
    assert m.gauge("load") == 0.9


def test_snapshot_contains_both(m):
    m.increment("a", 3)
    m.set_gauge("g", 1.5)
    snap = m.snapshot()
    assert snap["counters"]["a"] == 3
    assert snap["gauges"]["g"] == 1.5


def test_snapshot_is_copy(m):
    m.increment("a")
    snap = m.snapshot()
    m.increment("a")
    assert snap["counters"]["a"] == 1  # snapshot not affected


def test_reset_clears_all(m):
    m.increment("a")
    m.set_gauge("g", 9.0)
    m.reset()
    assert m.counter("a") == 0
    assert m.gauge("g") is None


def test_thread_safety(m):
    def worker():
        for _ in range(1000):
            m.increment("shared")

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert m.counter("shared") == 8000


def test_iter_counters(m):
    m.increment("x", 2)
    m.increment("y", 3)
    data = dict(m.iter_counters())
    assert data == {"x": 2, "y": 3}


def test_iter_gauges(m):
    m.set_gauge("p", 1.1)
    data = dict(m.iter_gauges())
    assert data == {"p": 1.1}
