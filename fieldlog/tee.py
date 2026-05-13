"""
fieldlog.tee
~~~~~~~~~~~~
Fan-out sink that forwards every entry to multiple downstream sinks,
collecting per-sink errors without dropping entries for healthy sinks.
"""
from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Tuple


class TeeSinkError(Exception):
    """Raised (optionally) when one or more sinks in a Tee fail."""

    def __init__(self, failures: List[Tuple[str, Exception]]) -> None:
        self.failures = failures
        names = ", ".join(name for name, _ in failures)
        super().__init__(f"Tee: {len(failures)} sink(s) failed: {names}")


class Tee:
    """Forward each log entry to every registered sink.

    Parameters
    ----------
    sinks:
        Iterable of callables that accept a single log-entry dict.
    raise_on_error:
        If *True* (default *False*) a :class:`TeeSinkError` is raised
        after all sinks have been attempted whenever at least one fails.
    names:
        Optional list of labels for each sink, used in error messages.
        Falls back to ``sink_0``, ``sink_1``, … when omitted.
    """

    def __init__(
        self,
        sinks: Iterable[Callable[[dict], None]],
        *,
        raise_on_error: bool = False,
        names: Optional[Iterable[str]] = None,
    ) -> None:
        self._sinks: List[Callable[[dict], None]] = list(sinks)
        if not self._sinks:
            raise ValueError("Tee requires at least one sink")
        self._raise_on_error = raise_on_error
        name_list = list(names) if names is not None else []
        self._names: List[str] = [
            name_list[i] if i < len(name_list) else f"sink_{i}"
            for i in range(len(self._sinks))
        ]
        self._error_counts: List[int] = [0] * len(self._sinks)

    # ------------------------------------------------------------------
    def __call__(self, entry: dict) -> None:
        failures: List[Tuple[str, Exception]] = []
        for i, (name, sink) in enumerate(zip(self._names, self._sinks)):
            try:
                sink(entry)
            except Exception as exc:  # noqa: BLE001
                self._error_counts[i] += 1
                failures.append((name, exc))
        if failures and self._raise_on_error:
            raise TeeSinkError(failures)

    # ------------------------------------------------------------------
    @property
    def error_counts(self) -> dict:
        """Return a mapping of sink name → cumulative error count."""
        return dict(zip(self._names, self._error_counts))

    def reset_error_counts(self) -> None:
        """Reset all per-sink error counters to zero."""
        self._error_counts = [0] * len(self._sinks)

    def __len__(self) -> int:  # number of registered sinks
        return len(self._sinks)

    def __repr__(self) -> str:
        return f"Tee(sinks={self._names!r}, raise_on_error={self._raise_on_error})"
