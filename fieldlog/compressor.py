"""
fieldlog.compressor
~~~~~~~~~~~~~~~~~~~
Optional compression layer for serialized log payloads.
Useful on edge devices where bandwidth or storage is constrained.
"""

import zlib
import lzma
from typing import Literal, Callable

Algorithm = Literal["zlib", "lzma"]

_MAGIC_ZLIB = b"\x00FLZ"
_MAGIC_LZMA = b"\x00FLL"


class Compressor:
    """Compress and decompress raw bytes using a chosen algorithm."""

    def __init__(self, algorithm: Algorithm = "zlib", level: int = 6) -> None:
        if algorithm not in ("zlib", "lzma"):
            raise ValueError(f"Unsupported algorithm: {algorithm!r}. Choose 'zlib' or 'lzma'.")
        self.algorithm: Algorithm = algorithm
        self.level = level

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compress(self, data: bytes) -> bytes:
        """Return compressed *data* prefixed with a magic header."""
        if self.algorithm == "zlib":
            return _MAGIC_ZLIB + zlib.compress(data, self.level)
        return _MAGIC_LZMA + lzma.compress(data, preset=min(self.level, 9))

    def decompress(self, data: bytes) -> bytes:
        """Decompress *data* previously produced by :meth:`compress`."""
        if data.startswith(_MAGIC_ZLIB):
            return zlib.decompress(data[len(_MAGIC_ZLIB):])
        if data.startswith(_MAGIC_LZMA):
            return lzma.decompress(data[len(_MAGIC_LZMA):])
        raise ValueError("Data does not contain a recognised fieldlog compression header.")

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def wrap_sink(self, sink: Callable[[bytes], None]) -> Callable[[bytes], None]:
        """Return a new callable that compresses bytes before passing them to *sink*."""
        def _compressed_sink(data: bytes) -> None:
            sink(self.compress(data))
        return _compressed_sink
