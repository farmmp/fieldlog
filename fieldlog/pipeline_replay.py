"""Pipeline integration for Replay — lets stored entries re-enter a Pipeline."""

from __future__ import annotations

from typing import Callable, Iterable, Optional

from fieldlog.replay import Replay, ReplayStats


class ReplayStage:
    """A pipeline-compatible stage that wraps :class:`~fieldlog.replay.Replay`.

    Typical usage::

        stage = ReplayStage(predicate=lambda e: e["level"] == "error")
        stage.bind(pipeline)
        stats = stage.run(stored_entries)

    Args:
        predicate: Optional filter applied before forwarding.
        transform: Optional callable applied to each entry before forwarding.
        delay: Inter-entry sleep in seconds (default 0).
    """

    def __init__(
        self,
        *,
        predicate: Optional[Callable[[dict], bool]] = None,
        transform: Optional[Callable[[dict], dict]] = None,
        delay: float = 0.0,
    ) -> None:
        self._predicate = predicate
        self._transform = transform
        self._delay = delay
        self._replay: Optional[Replay] = None

    def bind(self, sink: Callable[[dict], None]) -> "ReplayStage":
        """Attach *sink* (typically the next pipeline stage or output)."""
        self._replay = Replay(
            sink,
            predicate=self._predicate,
            transform=self._transform,
            delay=self._delay,
        )
        return self

    def run(self, entries: Iterable[dict]) -> ReplayStats:
        """Replay *entries* through the bound sink.

        Raises :class:`RuntimeError` if :meth:`bind` has not been called.
        """
        if self._replay is None:
            raise RuntimeError("ReplayStage.bind() must be called before run()")
        return self._replay.run(entries)

    @property
    def replayed(self) -> int:
        """Entries forwarded in the last :meth:`run` call (0 before first run)."""
        return self._replay.replayed if self._replay else 0

    @property
    def skipped(self) -> int:
        """Entries skipped in the last :meth:`run` call (0 before first run)."""
        return self._replay.skipped if self._replay else 0


def replay_pipeline(
    entries: Iterable[dict],
    sink: Callable[[dict], None],
    *,
    predicate: Optional[Callable[[dict], bool]] = None,
    transform: Optional[Callable[[dict], dict]] = None,
    delay: float = 0.0,
) -> ReplayStats:
    """Convenience function: replay *entries* directly into *sink*.

    Returns :class:`~fieldlog.replay.ReplayStats`.
    """
    stage = ReplayStage(predicate=predicate, transform=transform, delay=delay)
    stage.bind(sink)
    return stage.run(entries)
