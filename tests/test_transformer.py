"""Tests for fieldlog.transformer."""

from __future__ import annotations

import pytest

from fieldlog.transformer import (
    Transformer,
    TransformerPipeline,
    add_fields,
    drop_field,
    mask_field,
    rename_field,
)


def _entry(**kwargs):
    base = {"level": "info", "msg": "hello", "ts": 0}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# add_fields
# ---------------------------------------------------------------------------

def test_add_fields_merges():
    t = add_fields(env="prod", host="box1")
    result = t(_entry())
    assert result["env"] == "prod"
    assert result["host"] == "box1"


def test_add_fields_overrides_existing():
    t = add_fields(level="debug")
    result = t(_entry(level="info"))
    assert result["level"] == "debug"


# ---------------------------------------------------------------------------
# rename_field
# ---------------------------------------------------------------------------

def test_rename_field_moves_key():
    t = rename_field("msg", "message")
    result = t(_entry(msg="hi"))
    assert "message" in result
    assert "msg" not in result
    assert result["message"] == "hi"


def test_rename_field_missing_key_is_noop():
    t = rename_field("nonexistent", "other")
    entry = _entry()
    result = t(entry)
    assert result == entry


# ---------------------------------------------------------------------------
# drop_field
# ---------------------------------------------------------------------------

def test_drop_field_removes_key():
    t = drop_field("ts")
    result = t(_entry())
    assert "ts" not in result


def test_drop_multiple_fields():
    t = drop_field("ts", "level")
    result = t(_entry())
    assert "ts" not in result
    assert "level" not in result
    assert "msg" in result


# ---------------------------------------------------------------------------
# mask_field
# ---------------------------------------------------------------------------

def test_mask_field_replaces_value():
    t = mask_field("token")
    result = t(_entry(token="secret123"))
    assert result["token"] == "***"


def test_mask_field_custom_mask():
    t = mask_field("pw", mask="[REDACTED]")
    result = t(_entry(pw="hunter2"))
    assert result["pw"] == "[REDACTED]"


def test_mask_field_missing_key_is_noop():
    t = mask_field("missing")
    entry = _entry()
    assert t(entry) == entry


# ---------------------------------------------------------------------------
# Pipeline composition
# ---------------------------------------------------------------------------

def test_pipeline_via_or_operator():
    pipeline = add_fields(env="prod") | drop_field("ts")
    result = pipeline(_entry())
    assert result["env"] == "prod"
    assert "ts" not in result


def test_pipeline_drops_entry_on_none():
    def _nullify(entry):
        return None

    pipeline = TransformerPipeline([Transformer(_nullify), add_fields(env="prod")])
    assert pipeline(_entry()) is None


def test_pipeline_chain_three_transforms():
    pipeline = add_fields(service="svc") | rename_field("msg", "message") | mask_field("token")
    result = pipeline(_entry(token="abc"))
    assert result["service"] == "svc"
    assert "message" in result and "msg" not in result
    assert result["token"] == "***"
