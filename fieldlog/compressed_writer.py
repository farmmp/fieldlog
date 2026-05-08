"""
fieldlog.compressed_writer
~~~~~~~~~~~~~~~~~~~~~~~~~~
A :class:`~fieldlog.writer.BufferedFileWriter` variant that transparently
compresses each flushed batch before writing it to disk.
"""

import os
from pathlib import Path
from typing import Union

from .writer import BufferedFileWriter
from .compressor import Compressor, Algorithm


class CompressedFileWriter(BufferedFileWriter):
    """
    Drop-in replacement for :class:`BufferedFileWriter` that compresses
    every batch of serialized entries before appending to the log file.

    Files written by this class must be read back via
    :meth:`iter_batches` or decompressed manually with :class:`Compressor`.
    """

    def __init__(
        self,
        path: Union[str, Path],
        *,
        flush_threshold: int = 10,
        algorithm: Algorithm = "zlib",
        level: int = 6,
    ) -> None:
        super().__init__(path, flush_threshold=flush_threshold)
        self._compressor = Compressor(algorithm=algorithm, level=level)

    # ------------------------------------------------------------------
    # Overridden internals
    # ------------------------------------------------------------------

    def _write_batch(self, lines: list[bytes]) -> None:
        """Join *lines*, compress the block, and write a length-prefixed record."""
        raw = b"\n".join(lines) + b"\n"
        compressed = self._compressor.compress(raw)
        # 4-byte little-endian length prefix so batches can be split on read
        length_prefix = len(compressed).to_bytes(4, "little")
        with open(self._path, "ab") as fh:
            fh.write(length_prefix + compressed)

    # ------------------------------------------------------------------
    # Reading helper
    # ------------------------------------------------------------------

    def iter_batches(self):
        """Yield decompressed raw bytes for each batch stored in the file."""
        if not os.path.exists(self._path):
            return
        with open(self._path, "rb") as fh:
            while True:
                header = fh.read(4)
                if not header:
                    break
                length = int.from_bytes(header, "little")
                compressed = fh.read(length)
                yield self._compressor.decompress(compressed)
