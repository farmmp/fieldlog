"""
Redactor — scrubs or masks sensitive fields from log entries before forwarding.

Supports exact replacement, partial masking (keep N chars), and custom
redactor functions.  Designed to sit early in a pipeline so that PII /
credentials never reach downstream sinks.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional

_MASK = "***"


def _mask_partial(value: str, keep: int) -> str:
    """Keep the last *keep* characters and replace the rest with '*'."""
    s = str(value)
    if keep <= 0 or keep >= len(s):
        return _MASK
    return "*" * (len(s) - keep) + s[-keep:]


class Redactor:
    """
    Callable sink-wrapper that redacts nominated fields.

    Parameters
    ----------
    sink:
        Downstream callable that receives the scrubbed entry.
    fields:
        Iterable of field names to redact.
    mask:
        Replacement string used when *keep* is 0 (default ``"***"``).
    keep:
        If > 0, preserve the last *keep* characters of the original value
        and mask the rest.  Only applied to string values.
    custom:
        Mapping of field name → callable(value) → redacted_value.  Takes
        precedence over the default masking strategy for that field.
    """

    def __init__(
        self,
        sink: Callable[[Dict[str, Any]], None],
        fields: Iterable[str],
        *,
        mask: str = _MASK,
        keep: int = 0,
        custom: Optional[Dict[str, Callable[[Any], Any]]] = None,
    ) -> None:
        if not callable(sink):
            raise TypeError("sink must be callable")
        self._sink = sink
        self._fields: frozenset[str] = frozenset(fields)
        if not self._fields:
            raise ValueError("fields must not be empty")
        self._mask = mask
        self._keep = keep
        self._custom: Dict[str, Callable[[Any], Any]] = dict(custom or {})
        self._redacted_count = 0

    # ------------------------------------------------------------------
    # public interface
    # ------------------------------------------------------------------

    def __call__(self, entry: Dict[str, Any]) -> None:
        scrubbed = dict(entry)
        for field in self._fields:
            if field not in scrubbed:
                continue
            if field in self._custom:
                scrubbed[field] = self._custom[field](scrubbed[field])
            elif self._keep > 0 and isinstance(scrubbed[field], str):
                scrubbed[field] = _mask_partial(scrubbed[field], self._keep)
            else:
                scrubbed[field] = self._mask
            self._redacted_count += 1
        self._sink(scrubbed)

    @property
    def redacted_count(self) -> int:
        """Total number of field-level redactions performed."""
        return self._redacted_count

    def reset(self) -> None:
        """Reset the redaction counter."""
        self._redacted_count = 0
