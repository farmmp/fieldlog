"""Replay stored log entries through a sink, with optional filtering and rate control."""

from __future__ import annotations

import time
from typing import Callable, Iterable, Iterator, Optional


class ReplayError(Exception):
    """Raised when replay configuration is invalid."""


class Replay:
    """Reads persisted log entries and replays them through a sink.

    Args:
        sink: Callable that receives each replayed entry.
        predicate: Optional filter; only entries for which it returns True are replayed.
        delay: Seconds to sleep between entries (useful for rate-limiting replay).
        transform: Optional callable applied to each entry before forwarding.
    """

    def __init__(
        self,
        sink: Callable[[dict], None],
        *,
        predicate: Optional[Callable[[dict], bool]] = None,
        delay: float = 0.0,
        transform: Optional[Callable[[dict], dict]] = None,
    ) -> None:
        if not callable(sink):
            raise ReplayError("sink must be callable")
        if delay < 0:
            raise ReplayError("delay must be >= 0")
        self._sink = sink
        self._predicate = predicate
        self._delay = delay
        self._transform = transform
        self._replayed = 0
        self._skipped = 0

    def run(self, entries: Iterable[dict]) -> "ReplayStats":
        """Replay *entries* through the configured sink.

        Returns a :class:`ReplayStats` summary.
        """
        self._replayed = 0
        self._skipped = 0

        for entry in entries:
            if self._predicate is not None and not self._predicate(entry):
                self._skipped += 1
                continue

            out = self._transform(entry) if self._transform else entry
            self._sink(out)
            self._replayed += 1

            if self._delay > 0:
                time.sleep(self._delay)

        return ReplayStats(replayed=self._replayed, skipped=self._skipped)

    @property
    def replayed(self) -> int:
        """Number of entries forwarded to the sink in the last :meth:`run` call."""
        return self._replayed

    @property
    def skipped(self) -> int:
        """Number of entries skipped by the predicate in the last :meth:`run` call."""
        return self._skipped


class ReplayStats:
    """Immutable summary returned by :meth:`Replay.run`."""

    __slots__ = ("replayed", "skipped")

    def __init__(self, *, replayed: int, skipped: int) -> None:
        self.replayed = replayed
        self.skipped = skipped

    def __repr__(self) -> str:  # pragma: no cover
        return f"ReplayStats(replayed={self.replayed}, skipped={self.skipped})"
