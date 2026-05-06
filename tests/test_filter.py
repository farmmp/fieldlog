"""Tests for fieldlog.filter."""

import pytest

from fieldlog.filter import (
    Filter,
    apply_filter,
    by_field,
    by_level,
    by_tag,
)


def _e(level="INFO", tags=None, **kw):
    return {"level": level, "tags": tags or [], **kw}


# ---------------------------------------------------------------------------
# by_level
# ---------------------------------------------------------------------------

def test_by_level_min():
    flt = by_level(min_level="WARNING")
    assert flt(_e("WARNING"))
    assert flt(_e("ERROR"))
    assert not flt(_e("INFO"))
    assert not flt(_e("DEBUG"))


def test_by_level_range():
    flt = by_level(min_level="INFO", max_level="ERROR")
    assert flt(_e("INFO"))
    assert flt(_e("WARNING"))
    assert flt(_e("ERROR"))
    assert not flt(_e("DEBUG"))
    assert not flt(_e("CRITICAL"))


def test_by_level_unknown_level_excluded():
    flt = by_level(min_level="DEBUG")
    assert not flt({"level": "VERBOSE"})


# ---------------------------------------------------------------------------
# by_tag
# ---------------------------------------------------------------------------

def test_by_tag_single():
    flt = by_tag("gps")
    assert flt(_e(tags=["gps", "sensor"]))
    assert not flt(_e(tags=["sensor"]))


def test_by_tag_multiple_requires_all():
    flt = by_tag("gps", "sensor")
    assert flt(_e(tags=["gps", "sensor", "extra"]))
    assert not flt(_e(tags=["gps"]))


# ---------------------------------------------------------------------------
# by_field
# ---------------------------------------------------------------------------

def test_by_field_match():
    flt = by_field("device_id", "dev-42")
    assert flt({"device_id": "dev-42"})
    assert not flt({"device_id": "dev-99"})
    assert not flt({})


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------

def test_and_composition():
    flt = by_level(min_level="ERROR") & by_tag("critical")
    assert flt(_e("ERROR", tags=["critical"]))
    assert not flt(_e("ERROR", tags=[]))
    assert not flt(_e("INFO", tags=["critical"]))


def test_or_composition():
    flt = by_level(min_level="ERROR") | by_tag("urgent")
    assert flt(_e("ERROR"))
    assert flt(_e("INFO", tags=["urgent"]))
    assert not flt(_e("INFO"))


def test_invert():
    flt = ~by_level(min_level="WARNING")
    assert flt(_e("DEBUG"))
    assert not flt(_e("ERROR"))


# ---------------------------------------------------------------------------
# apply_filter
# ---------------------------------------------------------------------------

def test_apply_filter():
    entries = [_e("DEBUG"), _e("INFO"), _e("ERROR")]
    result = apply_filter(entries, by_level(min_level="INFO"))
    assert len(result) == 2
    assert all(e["level"] in ("INFO", "ERROR") for e in result)
