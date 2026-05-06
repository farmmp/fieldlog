"""Tests for fieldlog.writer.BufferedFileWriter."""

import json
from pathlib import Path

import pytest

from fieldlog.writer import BufferedFileWriter


@pytest.fixture
def log_file(tmp_path):
    return str(tmp_path / "test.log")


def _read_entries(path: str):
    lines = Path(path).read_bytes().splitlines()
    return [json.loads(line) for line in lines if line]


def test_write_and_flush(log_file):
    writer = BufferedFileWriter(log_file, flush_threshold=50)
    writer.write({"level": "INFO", "msg": "hello"})
    assert writer.pending == 1
    written = writer.flush()
    assert written == 1
    assert writer.pending == 0
    entries = _read_entries(log_file)
    assert entries[0]["msg"] == "hello"


def test_auto_flush_on_threshold(log_file):
    writer = BufferedFileWriter(log_file, maxsize=200, flush_threshold=5)
    for i in range(5):
        writer.write({"seq": i})
    # 5th write triggers auto-flush
    assert writer.pending == 0
    entries = _read_entries(log_file)
    assert len(entries) == 5


def test_multiple_flushes_append(log_file):
    writer = BufferedFileWriter(log_file, flush_threshold=100)
    writer.write({"batch": 1})
    writer.flush()
    writer.write({"batch": 2})
    writer.flush()
    entries = _read_entries(log_file)
    assert len(entries) == 2
    assert entries[1]["batch"] == 2


def test_flush_empty_returns_zero(log_file):
    writer = BufferedFileWriter(log_file)
    assert writer.flush() == 0


def test_rotate(log_file, tmp_path):
    writer = BufferedFileWriter(log_file, flush_threshold=100)
    writer.write({"msg": "before rotate"})
    rotated = writer.rotate()
    assert not Path(log_file).exists()
    assert rotated.exists()
    entries = _read_entries(str(rotated))
    assert entries[0]["msg"] == "before rotate"


def test_dropped_counter(log_file):
    writer = BufferedFileWriter(log_file, maxsize=3, flush_threshold=100)
    for i in range(5):
        writer.write({"seq": i})
    assert writer.dropped == 2
