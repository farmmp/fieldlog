"""Tests for fieldlog.compressor and fieldlog.compressed_writer."""

import pytest
from pathlib import Path

from fieldlog.compressor import Compressor
from fieldlog.compressed_writer import CompressedFileWriter


# ---------------------------------------------------------------------------
# Compressor unit tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("algo", ["zlib", "lzma"])
def test_roundtrip(algo):
    c = Compressor(algorithm=algo)
    original = b"{\"level\": \"info\", \"msg\": \"hello\"}"
    assert c.decompress(c.compress(original)) == original


def test_invalid_algorithm_raises():
    with pytest.raises(ValueError, match="Unsupported algorithm"):
        Compressor(algorithm="bz2")  # type: ignore[arg-type]


def test_decompress_bad_header_raises():
    c = Compressor()
    with pytest.raises(ValueError, match="recognised fieldlog compression header"):
        c.decompress(b"garbage data")


def test_compressed_is_smaller_for_repetitive_data():
    c = Compressor(algorithm="zlib")
    data = b"hello world " * 500
    assert len(c.compress(data)) < len(data)


def test_wrap_sink_compresses_before_forwarding():
    received: list[bytes] = []
    c = Compressor(algorithm="zlib")
    sink = c.wrap_sink(received.append)
    payload = b"some log line"
    sink(payload)
    assert len(received) == 1
    assert c.decompress(received[0]) == payload


# ---------------------------------------------------------------------------
# CompressedFileWriter integration tests
# ---------------------------------------------------------------------------

@pytest.fixture
def log_file(tmp_path) -> Path:
    return tmp_path / "compressed.log"


def test_write_and_read_back(log_file):
    writer = CompressedFileWriter(log_file, flush_threshold=3)
    for i in range(3):
        writer.write({"index": i, "level": "info"})
    writer.flush_all()

    batches = list(writer.iter_batches())
    assert len(batches) == 1
    lines = batches[0].strip().split(b"\n")
    assert len(lines) == 3


def test_multiple_batches_stored_and_read(log_file):
    writer = CompressedFileWriter(log_file, flush_threshold=2)
    for i in range(6):
        writer.write({"index": i})
    writer.flush_all()

    batches = list(writer.iter_batches())
    # 6 entries with threshold=2 → 3 batches
    assert len(batches) == 3


def test_iter_batches_empty_file_yields_nothing(log_file):
    writer = CompressedFileWriter(log_file)
    assert list(writer.iter_batches()) == []


def test_lzma_algorithm_roundtrip(log_file):
    writer = CompressedFileWriter(log_file, flush_threshold=1, algorithm="lzma")
    writer.write({"msg": "compressed with lzma"})
    writer.flush_all()
    batches = list(writer.iter_batches())
    assert b"lzma" in batches[0]
