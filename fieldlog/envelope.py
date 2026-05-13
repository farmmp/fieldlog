"""Envelope wraps log entries with routing metadata and transmission context."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Envelope:
    """Wraps a log entry with delivery metadata for reliable transmission."""

    entry: Dict[str, Any]
    envelope_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    attempt: int = 0
    origin: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)

    def next_attempt(self) -> "Envelope":
        """Return a new Envelope with attempt count incremented."""
        return Envelope(
            entry=self.entry,
            envelope_id=self.envelope_id,
            created_at=self.created_at,
            attempt=self.attempt + 1,
            origin=self.origin,
            tags=dict(self.tags),
        )

    def age(self, clock=time.time) -> float:
        """Return seconds elapsed since the envelope was created."""
        return clock() - self.created_at

    def is_expired(self, ttl: float, clock=time.time) -> bool:
        """Return True if the envelope's age exceeds the given TTL in seconds."""
        return self.age(clock=clock) > ttl

    def to_dict(self) -> Dict[str, Any]:
        """Serialise envelope to a plain dictionary."""
        return {
            "envelope_id": self.envelope_id,
            "created_at": self.created_at,
            "attempt": self.attempt,
            "origin": self.origin,
            "tags": self.tags,
            "entry": self.entry,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Envelope":
        """Reconstruct an Envelope from a plain dictionary."""
        return cls(
            entry=data["entry"],
            envelope_id=data["envelope_id"],
            created_at=data["created_at"],
            attempt=data.get("attempt", 0),
            origin=data.get("origin"),
            tags=data.get("tags", {}),
        )


def wrap(entry: Dict[str, Any], origin: Optional[str] = None, **tags: str) -> Envelope:
    """Convenience function to wrap a raw log entry in an Envelope."""
    return Envelope(entry=entry, origin=origin, tags=tags)
