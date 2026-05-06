"""Compact serialization helpers for log entries (JSON + msgpack)."""

import json
from datetime import datetime
from typing import Any, Dict

try:
    import msgpack  # type: ignore
    _MSGPACK_AVAILABLE = True
except ImportError:
    _MSGPACK_AVAILABLE = False


class _DatetimeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


def serialize_json(entry: Dict[str, Any], compact: bool = True) -> bytes:
    """Serialize a log entry to JSON bytes."""
    separators = (",", ":") if compact else (", ", ": ")
    return json.dumps(entry, cls=_DatetimeEncoder, separators=separators).encode("utf-8")


def deserialize_json(data: bytes) -> Dict[str, Any]:
    """Deserialize JSON bytes back to a log entry dict."""
    return json.loads(data.decode("utf-8"))


def serialize_msgpack(entry: Dict[str, Any]) -> bytes:
    """Serialize a log entry to msgpack bytes (requires msgpack package)."""
    if not _MSGPACK_AVAILABLE:
        raise RuntimeError("msgpack is not installed. Run: pip install msgpack")

    def _encode(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    sanitized = {k: _encode(v) for k, v in entry.items()}
    return msgpack.packb(sanitized, use_bin_type=True)


def deserialize_msgpack(data: bytes) -> Dict[str, Any]:
    """Deserialize msgpack bytes back to a log entry dict."""
    if not _MSGPACK_AVAILABLE:
        raise RuntimeError("msgpack is not installed. Run: pip install msgpack")
    return msgpack.unpackb(data, raw=False)


def get_serializer(fmt: str = "json"):
    """Return (serialize_fn, deserialize_fn) for the given format name."""
    if fmt == "json":
        return serialize_json, deserialize_json
    if fmt == "msgpack":
        return serialize_msgpack, deserialize_msgpack
    raise ValueError(f"Unknown serialization format: {fmt!r}. Choose 'json' or 'msgpack'.")
