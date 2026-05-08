"""A sink wrapper that validates entries against a Schema before forwarding."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from fieldlog.schema import Schema, SchemaError


class ValidatingSink:
    """Wraps a downstream sink and validates each entry.

    Parameters
    ----------
    sink:
        Callable that receives valid entries.
    schema:
        :class:`Schema` instance used for validation.  A default schema
        (requiring ``level`` and ``message``) is used when omitted.
    on_error:
        Optional callback ``(entry, exc) -> None`` invoked when validation
        fails.  If *None*, invalid entries are silently dropped.
    """

    def __init__(
        self,
        sink: Callable[[Dict[str, Any]], None],
        schema: Optional[Schema] = None,
        on_error: Optional[Callable[[Dict[str, Any], SchemaError], None]] = None,
    ) -> None:
        if not callable(sink):
            raise TypeError("sink must be callable")
        self._sink = sink
        self._schema = schema or Schema()
        self._on_error = on_error
        self._invalid_count = 0

    # ------------------------------------------------------------------
    def __call__(self, entry: Dict[str, Any]) -> None:
        try:
            self._schema.validate(entry)
        except SchemaError as exc:
            self._invalid_count += 1
            if self._on_error is not None:
                self._on_error(entry, exc)
            return
        self._sink(entry)

    # ------------------------------------------------------------------
    @property
    def invalid_count(self) -> int:
        """Total number of entries that failed validation."""
        return self._invalid_count

    def reset(self) -> None:
        """Reset the invalid-entry counter."""
        self._invalid_count = 0
