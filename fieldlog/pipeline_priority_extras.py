"""Higher-level helpers that integrate PriorityStage with the Pipeline API."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional

from fieldlog.priority_queue import _LEVEL_PRIORITY
from fieldlog.pipeline_priority import PriorityStage


def make_priority_sink(
    sink: Callable[[Dict[str, Any]], None],
    max_size: int = 0,
    auto_flush_on: Optional[Iterable[str]] = None,
) -> PriorityStage:
    """Create a :class:`PriorityStage` that optionally auto-flushes when a
    high-severity entry is received.

    Args:
        sink: Downstream callable.
        max_size: Buffer cap (0 = unbounded).
        auto_flush_on: Iterable of level names (e.g. ``["critical", "error"]``).
            When an entry at one of these levels is pushed, the buffer is
            flushed immediately after insertion.

    Returns:
        A bound :class:`PriorityStage` (with optional auto-flush wrapper).
    """
    stage = PriorityStage(max_size=max_size)
    stage.bind(sink)

    if not auto_flush_on:
        return stage

    trigger_levels = {lvl.lower() for lvl in auto_flush_on}

    class _AutoFlushStage:
        """Thin wrapper that delegates to *stage* and auto-flushes on triggers."""

        def __call__(self, entry: Dict[str, Any]) -> None:
            stage(entry)
            if str(entry.get("level", "")).lower() in trigger_levels:
                stage.flush()

        def flush(self) -> int:
            return stage.flush()

        @property
        def pending(self) -> int:
            return stage.pending

        @property
        def dropped_count(self) -> int:
            return stage.dropped_count

    return _AutoFlushStage()  # type: ignore[return-value]


def level_names_above(min_level: str) -> list:
    """Return all level names with priority <= *min_level* (i.e. at least as urgent).

    Useful to compute the ``auto_flush_on`` argument::

        auto_flush_on=level_names_above("error")  # ["critical", "error"]
    """
    threshold = _LEVEL_PRIORITY.get(min_level.lower())
    if threshold is None:
        raise ValueError(f"Unknown level: {min_level!r}. Known: {list(_LEVEL_PRIORITY)}")
    return [name for name, pri in _LEVEL_PRIORITY.items() if pri <= threshold]
