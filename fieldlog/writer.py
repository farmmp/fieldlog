"""Buffered writer that persists log entries to a local file."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .buffer import LogBuffer
from .serializer import get_serializer


class BufferedFileWriter:
    """Writes buffered log entries to a newline-delimited file.

    Entries accumulate in an in-memory LogBuffer and are flushed to
    disk either manually or when the buffer reaches `flush_threshold`.
    """

    def __init__(
        self,
        path: str,
        maxsize: int = 500,
        flush_threshold: int = 100,
        fmt: str = "json",
    ) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._buffer = LogBuffer(maxsize=maxsize)
        self._flush_threshold = flush_threshold
        self._serialize, _ = get_serializer(fmt)

    def write(self, entry: Dict[str, Any]) -> None:
        """Buffer a single log entry, auto-flushing if threshold is reached."""
        self._buffer.push(entry)
        if len(self._buffer) >= self._flush_threshold:
            self.flush()

    def flush(self, count: Optional[int] = None) -> int:
        """Flush buffered entries to disk. Returns the number written."""
        entries = self._buffer.flush(count)
        if not entries:
            return 0
        with self._path.open("ab") as fh:
            for entry in entries:
                fh.write(self._serialize(entry))
                fh.write(b"\n")
        return len(entries)

    def flush_all(self) -> int:
        """Flush every buffered entry to disk."""
        return self.flush()

    @property
    def pending(self) -> int:
        """Number of entries waiting to be flushed."""
        return len(self._buffer)

    @property
    def dropped(self) -> int:
        return self._buffer.dropped

    @property
    def path(self) -> Path:
        return self._path

    def rotate(self, dest: Optional[str] = None) -> Path:
        """Flush, then rename the log file to `dest` (or add .1 suffix)."""
        self.flush_all()
        target = Path(dest) if dest else self._path.with_suffix(".1" + self._path.suffix)
        os.rename(self._path, target)
        return target
