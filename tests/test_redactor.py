"""Tests for fieldlog.redactor."""

import pytest

from fieldlog.redactor import Redactor, _mask_partial


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _entry(**kwargs):
    base = {"level": "info", "msg": "hello"}
    base.update(kwargs)
    return base


@pytest.fixture()
def collected():
    return []


@pytest.fixture()
def sink(collected):
    return collected.append


# ---------------------------------------------------------------------------
# _mask_partial unit tests
# ---------------------------------------------------------------------------

def test_mask_partial_keeps_suffix():
    assert _mask_partial("secret123", 3) == "******123"


def test_mask_partial_keep_zero_returns_mask():
    assert _mask_partial("secret", 0) == "***"


def test_mask_partial_keep_ge_len_returns_mask():
    assert _mask_partial("hi", 10) == "***"


# ---------------------------------------------------------------------------
# constructor validation
# ---------------------------------------------------------------------------

def test_non_callable_sink_raises(sink):
    with pytest.raises(TypeError):
        Redactor("not-callable", fields=["password"])


def test_empty_fields_raises(sink):
    with pytest.raises(ValueError):
        Redactor(sink, fields=[])


# ---------------------------------------------------------------------------
# basic redaction
# ---------------------------------------------------------------------------

def test_field_is_masked(sink, collected):
    r = Redactor(sink, fields=["password"])
    r(_entry(password="s3cr3t"))
    assert collected[0]["password"] == "***"


def test_non_redacted_fields_unchanged(sink, collected):
    r = Redactor(sink, fields=["token"])
    r(_entry(token="abc", user="alice"))
    assert collected[0]["user"] == "alice"
    assert collected[0]["msg"] == "hello"


def test_missing_field_is_noop(sink, collected):
    r = Redactor(sink, fields=["secret"])
    r(_entry())  # no 'secret' key
    assert collected[0] == _entry()


def test_custom_mask_string(sink, collected):
    r = Redactor(sink, fields=["pin"], mask="[REDACTED]")
    r(_entry(pin="1234"))
    assert collected[0]["pin"] == "[REDACTED]"


# ---------------------------------------------------------------------------
# partial masking
# ---------------------------------------------------------------------------

def test_keep_preserves_suffix(sink, collected):
    r = Redactor(sink, fields=["card"], keep=4)
    r(_entry(card="4111111111111234"))
    assert collected[0]["card"].endswith("1234")
    assert "*" in collected[0]["card"]


def test_keep_on_non_string_falls_back_to_mask(sink, collected):
    r = Redactor(sink, fields=["pin"], keep=2)
    r(_entry(pin=9876))  # integer — cannot do suffix keep
    assert collected[0]["pin"] == "***"


# ---------------------------------------------------------------------------
# custom redactor functions
# ---------------------------------------------------------------------------

def test_custom_fn_applied(sink, collected):
    r = Redactor(sink, fields=["email"], custom={"email": lambda v: "<email>"})
    r(_entry(email="user@example.com"))
    assert collected[0]["email"] == "<email>"


def test_custom_fn_takes_precedence_over_keep(sink, collected):
    r = Redactor(sink, fields=["token"], keep=3,
                 custom={"token": lambda v: "CUSTOM"})
    r(_entry(token="abcdef"))
    assert collected[0]["token"] == "CUSTOM"


# ---------------------------------------------------------------------------
# counter
# ---------------------------------------------------------------------------

def test_redacted_count_increments(sink):
    r = Redactor(sink, fields=["a", "b"])
    r(_entry(a="x", b="y"))
    r(_entry(a="z"))
    assert r.redacted_count == 3


def test_reset_clears_count(sink):
    r = Redactor(sink, fields=["a"])
    r(_entry(a="x"))
    r.reset()
    assert r.redacted_count == 0


def test_original_entry_not_mutated(sink):
    r = Redactor(sink, fields=["secret"])
    original = _entry(secret="shh")
    r(original)
    assert original["secret"] == "shh"  # original must be untouched
