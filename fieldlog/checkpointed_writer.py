"""
CheckpointedFileWriter: wraps BufferedFileWriter with automatic checkpoint
management so that the last-flushed byte offset survives process restarts.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fieldlog.writer import BufferedFileWriter
from fieldlog.checkpoint import Checkpoint


class CheckpointedFileWriter:
    """
    A thin wrapper around :class:`~fieldlog.writer.BufferedFileWriter` that
    records the file byte-offset after every successful flush so the caller
    can detect and skip already-processed entries on restart.

    Parameters
    ----------
    log_path:
        Destination log file (passed through to ``BufferedFileWriter``).
    checkpoint_path:
        Where to persist the byte-offset checkpoint.
    threshold:
        Auto-flush threshold forwarded to ``BufferedFileWriter``.
    """

    def __init__(
        self,
        log_path: str,
        checkpoint_path: str,
        threshold: int = 10,
    ) -> None:
        self._writer = BufferedFileWriter(log_path, threshold=threshold)
        self._checkpoint = Checkpoint(checkpoint_path, key="byte_offset")
        self._log_path = log_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, entry: Dict[str, Any]) -> None:
        """Buffer *entry*; may trigger an auto-flush (and checkpoint update)."""
        self._writer.write(entry)
        # If the writer auto-flushed we won't know from here, so we only
        # checkpoint on explicit flush.  For guaranteed checkpointing call
        # flush() after write().

    def flush(self) -> None:
        """Flush buffered entries to disk and save the updated byte offset."""
        self._writer.flush()
        self._checkpoint.update(self._current_offset())
        self._checkpoint.save()

    def flush_all(self) -> None:
        """Flush all remaining entries and checkpoint."""
        self._writer.flush_all()
        self._checkpoint.update(self._current_offset())
        self._checkpoint.save()

    def resume_offset(self) -> Optional[int]:
        """
        Return the byte offset stored in the checkpoint file, or ``None`` if
        no checkpoint exists yet.  Callers can seek to this position when
        re-reading the log after a restart.
        """
        return self._checkpoint.load()  # type: ignore[return-value]

    def reset_checkpoint(self) -> None:
        """Delete the checkpoint file (e.g. when starting a fresh log)."""
        self._checkpoint.reset()

    @property
    def checkpoint(self) -> Checkpoint:
        """Direct access to the underlying :class:`Checkpoint` instance."""
        return self._checkpoint

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _current_offset(self) -> int:
        """Return the current size of the log file in bytes."""
        try:
            return os.path.getsize(self._log_path)
        except OSError:
            return 0
