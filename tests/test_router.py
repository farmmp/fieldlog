"""Tests for fieldlog.router."""

import pytest

from fieldlog.filter import by_level, by_tag
from fieldlog.router import LogRouter


def _e(level="INFO", tags=None, **kw):
    return {"level": level, "tags": tags or [], **kw}


@pytest.fixture()
def collected():
    """Returns a (sink, bucket) pair for capturing routed entries."""
    bucket: list = []
    return bucket.append, bucket


def test_dispatch_reaches_matching_sink(collected):
    sink, bucket = collected
    router = LogRouter()
    router.add_route(by_level(min_level="ERROR"), sink)

    router.dispatch(_e("ERROR"))
    router.dispatch(_e("INFO"))

    assert len(bucket) == 1
    assert bucket[0]["level"] == "ERROR"


def test_fanout_multiple_sinks():
    bucket_a, bucket_b = [], []
    router = LogRouter()
    router.add_route(by_level(min_level="DEBUG"), bucket_a.append)
    router.add_route(by_tag("important"), bucket_b.append)

    entry = _e("WARNING", tags=["important"])
    count = router.dispatch(entry)

    assert count == 2
    assert len(bucket_a) == 1
    assert len(bucket_b) == 1


def test_first_match_stops_early():
    bucket_a, bucket_b = [], []
    router = LogRouter(first_match=True)
    router.add_route(by_level(min_level="DEBUG"), bucket_a.append)
    router.add_route(by_level(min_level="DEBUG"), bucket_b.append)

    router.dispatch(_e("INFO"))

    assert len(bucket_a) == 1
    assert len(bucket_b) == 0


def test_chaining_returns_router():
    router = LogRouter()
    result = router.add_route(by_level(), lambda e: None)
    assert result is router


def test_len_reflects_route_count():
    router = LogRouter()
    assert len(router) == 0
    router.add_route(by_level(), lambda e: None)
    router.add_route(by_tag("x"), lambda e: None)
    assert len(router) == 2


def test_dispatch_many():
    bucket = []
    router = LogRouter()
    router.add_route(by_level(min_level="WARNING"), bucket.append)

    entries = [_e("DEBUG"), _e("WARNING"), _e("ERROR"), _e("INFO")]
    total = router.dispatch_many(entries)

    assert total == 2
    assert len(bucket) == 2


def test_no_matching_route_returns_zero():
    router = LogRouter()
    router.add_route(by_tag("never"), lambda e: None)
    assert router.dispatch(_e("CRITICAL")) == 0
