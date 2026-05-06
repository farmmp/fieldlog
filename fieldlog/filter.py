"""Log entry filtering for fieldlog.

Provides composable filters to selectively include or exclude log entries
based on level, tags, field values, or custom predicates.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

# Ordered severity levels
LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
_LEVEL_RANK = {lvl: i for i, lvl in enumerate(LEVELS)}


class Filter:
    """Composable log entry filter."""

    def __init__(self, predicate: Callable[[dict], bool]):
        self._predicate = predicate

    def __call__(self, entry: dict) -> bool:
        return self._predicate(entry)

    def __and__(self, other: "Filter") -> "Filter":
        return Filter(lambda e: self(e) and other(e))

    def __or__(self, other: "Filter") -> "Filter":
        return Filter(lambda e: self(e) or other(e))

    def __invert__(self) -> "Filter":
        return Filter(lambda e: not self(e))


def by_level(min_level: str = "DEBUG", max_level: str = "CRITICAL") -> Filter:
    """Keep entries whose level falls within [min_level, max_level]."""
    min_rank = _LEVEL_RANK.get(min_level.upper(), 0)
    max_rank = _LEVEL_RANK.get(max_level.upper(), len(LEVELS) - 1)

    def _check(entry: dict) -> bool:
        rank = _LEVEL_RANK.get((entry.get("level") or "").upper(), -1)
        return min_rank <= rank <= max_rank

    return Filter(_check)


def by_tag(*tags: str) -> Filter:
    """Keep entries that contain ALL of the given tags."""
    tag_set = set(tags)

    def _check(entry: dict) -> bool:
        entry_tags = set(entry.get("tags") or [])
        return tag_set.issubset(entry_tags)

    return Filter(_check)


def by_field(key: str, value: Any) -> Filter:
    """Keep entries where entry[key] == value."""
    return Filter(lambda e: e.get(key) == value)


def apply_filter(entries: Iterable[dict], flt: Filter) -> list[dict]:
    """Return a list of entries that pass *flt*."""
    return [e for e in entries if flt(e)]
