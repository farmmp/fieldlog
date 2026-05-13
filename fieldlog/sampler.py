"""Rate-based and deterministic sampling for log entries."""

import hashlib
import threading
from typing import Any, Callable, Dict, Optional


class Sampler:
    """Wraps a sink callable with sampling logic to reduce log volume."""

    def __init__(
        self,
        sink: Callable[[Dict[str, Any]], None],
        rate: float = 1.0,
        key_field: Optional[str] = None,
    ) -> None:
        """
        Args:
            sink:       Downstream callable that receives sampled entries.
            rate:       Fraction of entries to forward (0.0 – 1.0).
            key_field:  If set, sampling is deterministic based on this
                        entry field value instead of a counter.
        """
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"rate must be between 0.0 and 1.0, got {rate}")
        self._sink = sink
        self._rate = rate
        self._key_field = key_field
        self._counter = 0
        self._total = 0
        self._forwarded = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def __call__(self, entry: Dict[str, Any]) -> None:
        """Forward *entry* to the sink if it passes the sampling check."""
        if self._rate == 1.0:
            with self._lock:
                self._total += 1
                self._forwarded += 1
            self._sink(entry)
            return
        if self._rate == 0.0:
            with self._lock:
                self._total += 1
            return

        if self._key_field is not None:
            passed = self._deterministic_pass(entry)
        else:
            passed = self._counter_pass()

        if passed:
            self._sink(entry)

    @property
    def rate(self) -> float:
        return self._rate

    @property
    def stats(self) -> Dict[str, Any]:
        """Return a snapshot of sampling statistics.

        Returns:
            A dict with keys ``total`` (entries seen), ``forwarded``
            (entries passed to the sink), and ``effective_rate``
            (actual forwarded / total, or *None* if no entries seen yet).
        """
        with self._lock:
            total = self._total
            forwarded = self._forwarded
        effective_rate = forwarded / total if total > 0 else None
        return {"total": total, "forwarded": forwarded, "effective_rate": effective_rate}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _counter_pass(self) -> bool:
        """Increment a shared counter; forward every 1/rate-th entry."""
        with self._lock:
            self._total += 1
            self._counter += 1
            threshold = round(1.0 / self._rate)
            if self._counter >= threshold:
                self._counter = 0
                self._forwarded += 1
                return True
            return False

    def _deterministic_pass(self, entry: Dict[str, Any]) -> bool:
        """Hash the key field value and compare against rate bucket."""
        value = str(entry.get(self._key_field, ""))
        digest = hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF  # normalise to [0, 1]
        passed = bucket < self._rate
        with self._lock:
            self._total += 1
            if passed:
                self._forwarded += 1
        return passed
