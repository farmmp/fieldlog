"""EnvelopeSink unwraps Envelopes before forwarding entries to a downstream sink."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from fieldlog.envelope import Envelope


class EnvelopeSink:
    """Unwraps an Envelope and forwards the inner entry to a downstream sink.

    Optionally merges envelope metadata (origin, attempt, envelope_id) into
    the entry before forwarding, so downstream sinks see a flat log record.
    """

    def __init__(
        self,
        sink: Callable[[Dict[str, Any]], None],
        *,
        inject_metadata: bool = False,
        metadata_prefix: str = "_env_",
    ) -> None:
        if not callable(sink):
            raise TypeError("sink must be callable")
        self._sink = sink
        self._inject = inject_metadata
        self._prefix = metadata_prefix
        self._forwarded = 0
        self._rejected = 0

    def __call__(self, envelope: Any) -> None:
        if not isinstance(envelope, Envelope):
            self._rejected += 1
            raise TypeError(
                f"EnvelopeSink expects an Envelope, got {type(envelope).__name__}"
            )
        entry = dict(envelope.entry)
        if self._inject:
            p = self._prefix
            entry[f"{p}id"] = envelope.envelope_id
            entry[f"{p}attempt"] = envelope.attempt
            if envelope.origin is not None:
                entry[f"{p}origin"] = envelope.origin
            for k, v in envelope.tags.items():
                entry[f"{p}tag_{k}"] = v
        self._sink(entry)
        self._forwarded += 1

    @property
    def forwarded(self) -> int:
        """Number of envelopes successfully unwrapped and forwarded."""
        return self._forwarded

    @property
    def rejected(self) -> int:
        """Number of non-Envelope objects that were rejected."""
        return self._rejected
