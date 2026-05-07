"""Entry transformer pipeline for fieldlog.

Allows chaining of callables that mutate or enrich log entries
before they are dispatched to sinks.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional

Entry = Dict[str, Any]
TransformFn = Callable[[Entry], Optional[Entry]]


class Transformer:
    """Wraps a single transform function with a friendly API."""

    def __init__(self, fn: TransformFn) -> None:
        self._fn = fn

    def __call__(self, entry: Entry) -> Optional[Entry]:
        return self._fn(entry)

    def __or__(self, other: "Transformer") -> "TransformerPipeline":
        """Compose two transformers into a pipeline via | operator."""
        return TransformerPipeline([self, other])


class TransformerPipeline:
    """Applies a sequence of transformers in order.

    If any transformer returns None the entry is dropped and
    subsequent transformers are skipped.
    """

    def __init__(self, transformers: Iterable[TransformFn]) -> None:
        self._transformers: list[TransformFn] = list(transformers)

    def __call__(self, entry: Entry) -> Optional[Entry]:
        current: Optional[Entry] = entry
        for t in self._transformers:
            if current is None:
                return None
            current = t(current)
        return current

    def __or__(self, other: TransformFn) -> "TransformerPipeline":
        return TransformerPipeline(self._transformers + [other])


# ---------------------------------------------------------------------------
# Built-in factory helpers
# ---------------------------------------------------------------------------

def add_fields(**fields: Any) -> Transformer:
    """Return a transformer that merges *fields* into every entry."""
    def _fn(entry: Entry) -> Entry:
        return {**entry, **fields}
    return Transformer(_fn)


def rename_field(src: str, dst: str) -> Transformer:
    """Return a transformer that renames key *src* to *dst*."""
    def _fn(entry: Entry) -> Entry:
        if src not in entry:
            return entry
        updated = dict(entry)
        updated[dst] = updated.pop(src)
        return updated
    return Transformer(_fn)


def drop_field(*keys: str) -> Transformer:
    """Return a transformer that removes *keys* from the entry."""
    key_set = set(keys)
    def _fn(entry: Entry) -> Entry:
        return {k: v for k, v in entry.items() if k not in key_set}
    return Transformer(_fn)


def mask_field(key: str, mask: str = "***") -> Transformer:
    """Return a transformer that replaces the value of *key* with *mask*."""
    def _fn(entry: Entry) -> Entry:
        if key not in entry:
            return entry
        return {**entry, key: mask}
    return Transformer(_fn)
