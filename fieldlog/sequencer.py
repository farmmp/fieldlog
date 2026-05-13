"""
Sequencer — assigns monotonically increasing sequence numbers to log entries.

Useful for detecting gaps or reordering in low-connectivity environments
where entries may arrive out of order or be lost in transit.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

LogEntry = Dict[str, Any]
Sink = Callable[[LogEntry], None]


class Sequencer:
    """
    Wraps a sink and stamps each passing entry with a ``seq`` field.

    Parameters
    ----------
    sink:
        Downstream callable that receives the stamped entry.
    field:
        Name of the field written onto each entry.  Defaults to ``"seq"``.
    start:
        First sequence number.  Defaults to ``0``.
    overwrite:
        When *False* (default) an entry that already carries the field is
        forwarded unchanged.  When *True* the existing value is replaced.
    """

    def __init__(
        self,
        sink: Sink,
        *,
        field: str = "seq",
        start: int = 0,
        overwrite: bool = False,
    ) -> None:
        if not callable(sink):
            raise TypeError("sink must be callable")
        if not isinstance(start, int):
            raise TypeError("start must be an int")
        if start < 0:
            raise ValueError("start must be >= 0")

        self._sink = sink
        self._field = field
        self._counter = start
        self._overwrite = overwrite
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def __call__(self, entry: LogEntry) -> None:
        """Stamp *entry* with the next sequence number and forward it."""
        with self._lock:
            if self._overwrite or self._field not in entry:
                stamped = {**entry, self._field: self._counter}
                self._counter += 1
            else:
                stamped = entry
        self._sink(stamped)

    @property
    def current(self) -> int:
        """Next sequence number that will be assigned."""
        with self._lock:
            return self._counter

    def reset(self, value: int = 0) -> None:
        """Reset the counter to *value* (default ``0``)."""
        if not isinstance(value, int) or value < 0:
            raise ValueError("value must be a non-negative int")
        with self._lock:
            self._counter = value
