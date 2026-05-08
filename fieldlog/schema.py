"""Schema validation for log entries."""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional


class SchemaError(Exception):
    """Raised when a log entry fails schema validation."""


_LEVEL_VALUES = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}


def _check_required(entry: Dict[str, Any], fields: Iterable[str]) -> None:
    missing = [f for f in fields if f not in entry]
    if missing:
        raise SchemaError(f"Missing required fields: {missing}")


def _check_types(entry: Dict[str, Any], type_map: Dict[str, type]) -> None:
    for field, expected in type_map.items():
        if field in entry and not isinstance(entry[field], expected):
            raise SchemaError(
                f"Field '{field}' expected {expected.__name__}, "
                f"got {type(entry[field]).__name__}"
            )


def _check_level(entry: Dict[str, Any]) -> None:
    level = entry.get("level")
    if level is not None and level not in _LEVEL_VALUES:
        raise SchemaError(
            f"Unknown level '{level}'. Valid: {list(_LEVEL_VALUES)}"
        )


class Schema:
    """Validates log entry dicts against a set of rules."""

    def __init__(
        self,
        required: Optional[Iterable[str]] = None,
        type_map: Optional[Dict[str, type]] = None,
        validate_level: bool = True,
        extra_validators: Optional[Iterable[Callable[[Dict[str, Any]], None]]] = None,
    ) -> None:
        self._required = list(required or ["level", "message"])
        self._type_map: Dict[str, type] = type_map or {"message": str}
        self._validate_level = validate_level
        self._extra: list[Callable[[Dict[str, Any]], None]] = list(extra_validators or [])

    def validate(self, entry: Dict[str, Any]) -> None:
        """Raise SchemaError if *entry* is invalid."""
        _check_required(entry, self._required)
        _check_types(entry, self._type_map)
        if self._validate_level:
            _check_level(entry)
        for validator in self._extra:
            validator(entry)

    def __call__(self, entry: Dict[str, Any]) -> None:
        self.validate(entry)
