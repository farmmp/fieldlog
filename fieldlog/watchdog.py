"""Watchdog sink: raises an alert if no entries are received within a timeout window."""

import threading
import time
from typing import Callable, Optional


def _default_clock() -> float:
    return time.monotonic()


class WatchdogError(Exception):
    """Raised when the watchdog fires due to inactivity."""


class Watchdog:
    """Wraps a sink and triggers an alert callable if no entry arrives within *timeout* seconds.

    The watchdog runs a background daemon thread.  Call :meth:`stop` to
    cancel it when the sink is no longer needed.

    Args:
        sink:      Downstream callable that receives each log entry.
        timeout:   Seconds of inactivity before *on_alert* is called.
        on_alert:  Callable invoked with ``(elapsed: float)`` when the
                   watchdog fires.  Defaults to raising :class:`WatchdogError`.
        clock:     Callable returning current time (monotonic seconds).
    """

    def __init__(
        self,
        sink: Callable,
        timeout: float,
        on_alert: Optional[Callable[[float], None]] = None,
        clock: Callable[[], float] = _default_clock,
    ) -> None:
        if not callable(sink):
            raise TypeError("sink must be callable")
        if timeout <= 0:
            raise ValueError("timeout must be > 0")

        self._sink = sink
        self._timeout = timeout
        self._clock = clock
        self._last_seen: float = clock()
        self._stopped = threading.Event()
        self._lock = threading.Lock()

        if on_alert is None:
            def on_alert(elapsed: float) -> None:  # type: ignore[misc]
                raise WatchdogError(
                    f"No log entries received for {elapsed:.1f}s (timeout={timeout}s)"
                )
        self._on_alert = on_alert

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    def __call__(self, entry: dict) -> None:
        with self._lock:
            self._last_seen = self._clock()
        self._sink(entry)

    # ------------------------------------------------------------------
    def stop(self) -> None:
        """Stop the background watchdog thread."""
        self._stopped.set()

    @property
    def last_seen(self) -> float:
        with self._lock:
            return self._last_seen

    # ------------------------------------------------------------------
    def _run(self) -> None:
        while not self._stopped.wait(timeout=min(self._timeout / 4, 1.0)):
            now = self._clock()
            with self._lock:
                elapsed = now - self._last_seen
            if elapsed >= self._timeout:
                self._on_alert(elapsed)
