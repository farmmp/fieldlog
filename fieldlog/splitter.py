"""fieldlog.splitter
~~~~~~~~~~~~~~~~~
Routes log entries to different sinks based on a key extracted from
each entry.  Useful for fan-out by severity tier, tenant, or any
arbitrary string dimension without writing a full LogRouter.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional


class SplitterError(Exception):
    """Raised for invalid Splitter configuration."""


class Splitter:
    """Dispatch log entries to per-key sinks.

    Parameters
    ----------
    key_fn:
        Callable that receives a log-entry dict and returns a string key.
    sinks:
        Mapping of key -> callable sink.  Entries whose key is absent from
        the mapping are forwarded to *default_sink* (if provided) or dropped.
    default_sink:
        Optional fallback sink for unmatched keys.
    """

    def __init__(
        self,
        key_fn: Callable[[Dict[str, Any]], str],
        sinks: Dict[str, Callable[[Dict[str, Any]], None]],
        default_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        if not callable(key_fn):
            raise SplitterError("key_fn must be callable")
        if not sinks:
            raise SplitterError("sinks mapping must not be empty")
        for k, s in sinks.items():
            if not callable(s):
                raise SplitterError(f"sink for key {k!r} is not callable")
        if default_sink is not None and not callable(default_sink):
            raise SplitterError("default_sink must be callable")

        self._key_fn = key_fn
        self._sinks: Dict[str, Callable[[Dict[str, Any]], None]] = dict(sinks)
        self._default_sink = default_sink
        self._dropped = 0

    # ------------------------------------------------------------------
    def __call__(self, entry: Dict[str, Any]) -> None:
        key = self._key_fn(entry)
        sink = self._sinks.get(key, self._default_sink)
        if sink is None:
            self._dropped += 1
            return
        sink(entry)

    # ------------------------------------------------------------------
    @property
    def dropped_count(self) -> int:
        """Number of entries dropped because no matching sink was found."""
        return self._dropped

    def keys(self):
        """Return the registered sink keys."""
        return self._sinks.keys()

    def add_sink(
        self, key: str, sink: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Register or replace the sink for *key* at runtime."""
        if not callable(sink):
            raise SplitterError(f"sink for key {key!r} is not callable")
        self._sinks[key] = sink

    def remove_sink(self, key: str) -> None:
        """Remove the sink registered for *key*.

        Parameters
        ----------
        key:
            The sink key to remove.

        Raises
        ------
        SplitterError
            If *key* is not currently registered, or if removing it would
            leave the splitter with no sinks and no default_sink.
        """
        if key not in self._sinks:
            raise SplitterError(f"no sink registered for key {key!r}")
        if len(self._sinks) == 1 and self._default_sink is None:
            raise SplitterError(
                f"cannot remove the last sink {key!r} without a default_sink"
            )
        del self._sinks[key]

    def reset_dropped(self) -> None:
        """Reset the dropped-entry counter."""
        self._dropped = 0
