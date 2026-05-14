"""Pipeline integration for :class:`~fieldlog.watchdog.Watchdog`."""

from typing import Callable, Optional

from fieldlog.watchdog import Watchdog, _default_clock
from fieldlog.pipeline import Pipeline


class WatchdogStage:
    """A pipeline stage that wraps the next sink in a :class:`Watchdog`.

    Args:
        timeout:   Inactivity timeout in seconds.
        on_alert:  Optional alert callback ``(elapsed: float) -> None``.
        clock:     Time source (defaults to ``time.monotonic``).
    """

    def __init__(
        self,
        timeout: float,
        on_alert: Optional[Callable[[float], None]] = None,
        clock: Callable[[], float] = _default_clock,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self._timeout = timeout
        self._on_alert = on_alert
        self._clock = clock
        self._watchdog: Optional[Watchdog] = None

    def bind(self, next_sink: Callable) -> "WatchdogStage":
        """Attach *next_sink* and create the underlying :class:`Watchdog`."""
        self._watchdog = Watchdog(
            sink=next_sink,
            timeout=self._timeout,
            on_alert=self._on_alert,
            clock=self._clock,
        )
        return self

    def __call__(self, entry: dict) -> None:
        if self._watchdog is None:
            raise RuntimeError("WatchdogStage has not been bound to a sink; call bind() first")
        self._watchdog(entry)

    def stop(self) -> None:
        """Stop the underlying watchdog thread."""
        if self._watchdog is not None:
            self._watchdog.stop()

    @property
    def dropped_count(self) -> int:  # satisfies Pipeline stage interface
        return 0


def watchdog_pipeline(
    timeout: float,
    sink: Callable,
    on_alert: Optional[Callable[[float], None]] = None,
    clock: Callable[[], float] = _default_clock,
) -> Pipeline:
    """Convenience factory: build a single-stage :class:`Pipeline` with a watchdog.

    Example::

        pipe = watchdog_pipeline(timeout=30, sink=my_sink)
        pipe(entry)   # forwarded; watchdog resets
        pipe.stop()   # stop background thread when done

    Args:
        timeout:   Seconds of inactivity before *on_alert* fires.
        sink:      Terminal sink for log entries.
        on_alert:  Optional alert callback.
        clock:     Time source.

    Returns:
        A :class:`~fieldlog.pipeline.Pipeline` instance.
    """
    stage = WatchdogStage(timeout=timeout, on_alert=on_alert, clock=clock)
    stage.bind(sink)
    p = Pipeline(sink=stage)
    return p
