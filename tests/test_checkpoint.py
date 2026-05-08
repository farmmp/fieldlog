import json
import os
import pytest

from fieldlog.checkpoint import Checkpoint, CheckpointError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def cp(tmp_path):
    return Checkpoint(str(tmp_path / "state" / "cursor.json"))


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_empty_path_raises():
    with pytest.raises(ValueError):
        Checkpoint("")


def test_initial_value_is_none(cp):
    assert cp.value is None


def test_initial_not_dirty(cp):
    assert not cp.is_dirty


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

def test_load_returns_none_when_file_absent(cp):
    result = cp.load()
    assert result is None


def test_load_reads_existing_file(tmp_path):
    p = tmp_path / "cp.json"
    p.write_text(json.dumps({"position": 42}))
    cp = Checkpoint(str(p))
    assert cp.load() == 42
    assert cp.value == 42


def test_load_custom_key(tmp_path):
    p = tmp_path / "cp.json"
    p.write_text(json.dumps({"offset": 99}))
    cp = Checkpoint(str(p), key="offset")
    assert cp.load() == 99


def test_load_bad_json_raises(tmp_path):
    p = tmp_path / "cp.json"
    p.write_text("not json{{{")
    cp = Checkpoint(str(p))
    with pytest.raises(CheckpointError):
        cp.load()


# ---------------------------------------------------------------------------
# update / save
# ---------------------------------------------------------------------------

def test_update_sets_value_and_dirty(cp):
    cp.update(100)
    assert cp.value == 100
    assert cp.is_dirty


def test_save_persists_value(cp):
    cp.update("2024-01-01T00:00:00")
    cp.save()
    assert not cp.is_dirty
    raw = json.loads(open(cp._path).read())
    assert raw["position"] == "2024-01-01T00:00:00"


def test_save_creates_intermediate_dirs(tmp_path):
    deep = str(tmp_path / "a" / "b" / "c" / "cp.json")
    cp = Checkpoint(deep)
    cp.update(7)
    cp.save()
    assert os.path.exists(deep)


def test_load_after_save_roundtrip(cp):
    cp.update(555)
    cp.save()
    cp2 = Checkpoint(cp._path)
    assert cp2.load() == 555


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------

def test_reset_clears_value(cp):
    cp.update(10)
    cp.save()
    cp.reset()
    assert cp.value is None
    assert not cp.is_dirty


def test_reset_removes_file(cp):
    cp.update(1)
    cp.save()
    assert os.path.exists(cp._path)
    cp.reset()
    assert not os.path.exists(cp._path)


def test_reset_on_missing_file_is_noop(cp):
    cp.reset()  # should not raise
