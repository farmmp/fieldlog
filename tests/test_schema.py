"""Tests for fieldlog.schema."""
import pytest

from fieldlog.schema import Schema, SchemaError


def _entry(**kw):
    base = {"level": "info", "message": "hello"}
    base.update(kw)
    return base


def test_valid_entry_passes():
    Schema().validate(_entry())


def test_missing_required_raises():
    with pytest.raises(SchemaError, match="Missing required fields"):
        Schema().validate({"level": "info"})  # no 'message'


def test_custom_required_fields():
    schema = Schema(required=["level", "message", "device_id"])
    with pytest.raises(SchemaError, match="device_id"):
        schema.validate(_entry())


def test_wrong_type_raises():
    schema = Schema(type_map={"message": str})
    with pytest.raises(SchemaError, match="message"):
        schema.validate({"level": "info", "message": 42})


def test_unknown_level_raises():
    with pytest.raises(SchemaError, match="Unknown level"):
        Schema().validate(_entry(level="verbose"))


def test_validate_level_false_skips_level_check():
    schema = Schema(validate_level=False)
    schema.validate(_entry(level="custom"))  # should not raise


def test_extra_validator_called():
    calls = []

    def must_have_ts(entry):
        if "ts" not in entry:
            raise SchemaError("ts required")
        calls.append(entry)

    schema = Schema(extra_validators=[must_have_ts])
    with pytest.raises(SchemaError, match="ts required"):
        schema.validate(_entry())

    schema.validate(_entry(ts="2024-01-01"))
    assert len(calls) == 1


def test_callable_interface():
    schema = Schema()
    schema(_entry())  # __call__ should not raise
    with pytest.raises(SchemaError):
        schema({"level": "info"})  # missing message
