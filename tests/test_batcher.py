import pytest
from fieldlog.batcher import Batcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(msg: str = "hello", level: str = "INFO") -> dict:
    return {"message": msg, "level": level}


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def __call__(self) -> float:
        return self._t

    def advance(self, seconds: float) -> None:
        self._t += seconds


def _collecting_sink():
    batches = []

    def sink(batch):
        batches.append(list(batch))

    sink.batches = batches
    return sink


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_invalid_max_size_raises():
    with pytest.raises(ValueError, match="max_size"):
        Batcher(sink=lambda b: None, max_size=0)


def test_invalid_max_age_raises():
    with pytest.raises(ValueError, match="max_age_seconds"):
        Batcher(sink=lambda b: None, max_age_seconds=0)


# ---------------------------------------------------------------------------
# Size-based flushing
# ---------------------------------------------------------------------------

def test_flush_on_size_threshold():
    sink = _collecting_sink()
    batcher = Batcher(sink, max_size=3, max_age_seconds=60)

    batcher(_entry("a"))
    batcher(_entry("b"))
    assert sink.batches == []  # not yet
    batcher(_entry("c"))      # triggers flush

    assert len(sink.batches) == 1
    assert len(sink.batches[0]) == 3


def test_pending_count_resets_after_flush():
    sink = _collecting_sink()
    batcher = Batcher(sink, max_size=2, max_age_seconds=60)

    batcher(_entry())
    assert batcher.pending == 1
    batcher(_entry())  # flush
    assert batcher.pending == 0


# ---------------------------------------------------------------------------
# Age-based flushing
# ---------------------------------------------------------------------------

def test_flush_on_age_threshold():
    clock = _FakeClock()
    sink = _collecting_sink()
    batcher = Batcher(sink, max_size=100, max_age_seconds=5.0, clock=clock)

    batcher(_entry("first"))
    clock.advance(4.9)
    batcher(_entry("second"))  # age not yet reached
    assert sink.batches == []

    clock.advance(0.2)         # total age > 5 s
    batcher(_entry("third"))   # triggers flush

    assert len(sink.batches) == 1
    assert len(sink.batches[0]) == 3


# ---------------------------------------------------------------------------
# Manual flush
# ---------------------------------------------------------------------------

def test_manual_flush_sends_partial_batch():
    sink = _collecting_sink()
    batcher = Batcher(sink, max_size=10, max_age_seconds=60)

    batcher(_entry("x"))
    batcher(_entry("y"))
    n = batcher.flush()

    assert n == 2
    assert len(sink.batches) == 1
    assert batcher.pending == 0


def test_manual_flush_empty_returns_zero():
    sink = _collecting_sink()
    batcher = Batcher(sink, max_size=5, max_age_seconds=60)
    assert batcher.flush() == 0
    assert sink.batches == []


# ---------------------------------------------------------------------------
# Multiple batches
# ---------------------------------------------------------------------------

def test_multiple_batches_accumulate():
    sink = _collecting_sink()
    batcher = Batcher(sink, max_size=2, max_age_seconds=60)

    for i in range(6):
        batcher(_entry(str(i)))

    assert len(sink.batches) == 3
    assert all(len(b) == 2 for b in sink.batches)
