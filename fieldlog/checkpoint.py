"""
Checkpoint: persists the last successfully flushed log position to disk
so that on restart the pipeline can resume without re-processing entries.
"""

from __future__ import annotations

import json
import os
from typing import Optional


class CheckpointError(Exception):
    """Raised when a checkpoint file cannot be read or written."""


class Checkpoint:
    """
    Stores and retrieves a named cursor value (e.g. a byte offset, sequence
    number, or ISO timestamp) in a small JSON file.

    Parameters
    ----------
    path:
        File path used to persist the checkpoint.
    key:
        Logical name for the cursor (default ``"position"``).
    """

    def __init__(self, path: str, key: str = "position") -> None:
        if not path:
            raise ValueError("path must be a non-empty string")
        self._path = path
        self._key = key
        self._value: Optional[object] = None
        self._dirty: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def value(self) -> Optional[object]:
        """Current in-memory cursor value (``None`` if never set)."""
        return self._value

    def load(self) -> Optional[object]:
        """Load cursor from disk.  Returns ``None`` if the file is absent."""
        if not os.path.exists(self._path):
            return None
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise CheckpointError(f"Cannot read checkpoint {self._path!r}: {exc}") from exc
        self._value = data.get(self._key)
        self._dirty = False
        return self._value

    def update(self, value: object) -> None:
        """Update the in-memory cursor value (does **not** write to disk)."""
        self._value = value
        self._dirty = True

    def save(self) -> None:
        """Persist the current cursor value to disk."""
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump({self._key: self._value}, fh)
        except OSError as exc:
            raise CheckpointError(f"Cannot write checkpoint {self._path!r}: {exc}") from exc
        self._dirty = False

    def reset(self) -> None:
        """Clear the in-memory cursor and remove the checkpoint file if present."""
        self._value = None
        self._dirty = False
        if os.path.exists(self._path):
            os.remove(self._path)

    @property
    def is_dirty(self) -> bool:
        """``True`` if the cursor has been updated since the last save."""
        return self._dirty
