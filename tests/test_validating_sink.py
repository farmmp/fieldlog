"""Tests for fieldlog.validating_sink."""
import pytest

from fieldlog.schema import Schema, SchemaError
from fieldlog.validating_sink import ValidatingSink


def _entry(**kw):
    base = {"level": "info", "message": "ok"}
    base.update(kw)
    return base


@pytest.fixture
def collected():
    return []


@pytest.fixture
def sink(collected):
    return ValidatingSink(collected.append)


def test_non_callable_raises():
    with pytest.raises(TypeError):
        ValidatingSink("not_callable")


def test_valid_entry_forwarded(sink, collected):
    sink(_entry())
    assert len(collected) == 1


def test_invalid_entry_dropped(sink, collected):
    sink({"level": "info"})  # missing message
    assert collected == []


def test_invalid_count_increments(sink):
    sink({"level": "info"})  # invalid
    sink({"level": "info"})  # invalid
    assert sink.invalid_count == 2


def test_valid_entry_does_not_increment_count(sink):
    sink(_entry())
    assert sink.invalid_count == 0


def test_on_error_callback_invoked(collected):
    errors = []
    s = ValidatingSink(collected.append, on_error=lambda e, exc: errors.append((e, exc)))
    bad = {"level": "info"}  # missing message
    s(bad)
    assert len(errors) == 1
    assert errors[0][0] is bad
    assert isinstance(errors[0][1], SchemaError)


def test_reset_clears_count(sink):
    sink({"level": "info"})  # invalid
    assert sink.invalid_count == 1
    sink.reset()
    assert sink.invalid_count == 0


def test_custom_schema_enforced(collected):
    schema = Schema(required=["level", "message", "device_id"])
    s = ValidatingSink(collected.append, schema=schema)
    s(_entry())           # missing device_id → dropped
    assert collected == []
    s(_entry(device_id="dev-1"))
    assert len(collected) == 1


def test_mixed_valid_invalid(sink, collected):
    sink(_entry())
    sink({"level": "info"})  # invalid
    sink(_entry(message="second"))
    assert len(collected) == 2
    assert sink.invalid_count == 1
