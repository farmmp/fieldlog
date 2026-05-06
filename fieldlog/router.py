"""Log router for fieldlog.

Routes log entries through a pipeline of filters and writers so that
different entries can be directed to different destinations.
"""

from __future__ import annotations

from typing import Callable, List, Tuple

from fieldlog.filter import Filter

# A sink is any callable that accepts a single log-entry dict.
Sink = Callable[[dict], None]


class Route:
    """A (filter, sink) pair."""

    def __init__(self, flt: Filter, sink: Sink):
        self.flt = flt
        self.sink = sink

    def process(self, entry: dict) -> bool:
        """Send *entry* to sink if it passes the filter. Returns True if sent."""
        if self.flt(entry):
            self.sink(entry)
            return True
        return False


class LogRouter:
    """Routes each log entry to one or more matching sinks.

    By default every matching route receives the entry (fan-out).  Set
    ``first_match=True`` to stop after the first matching route.
    """

    def __init__(self, first_match: bool = False):
        self._routes: List[Route] = []
        self.first_match = first_match

    def add_route(self, flt: Filter, sink: Sink) -> "LogRouter":
        """Register a route and return *self* for chaining."""
        self._routes.append(Route(flt, sink))
        return self

    def dispatch(self, entry: dict) -> int:
        """Dispatch *entry* to all matching sinks. Returns count of sinks reached."""
        count = 0
        for route in self._routes:
            if route.process(entry):
                count += 1
                if self.first_match:
                    break
        return count

    def dispatch_many(self, entries: list[dict]) -> int:
        """Dispatch a batch of entries. Returns total sinks reached."""
        return sum(self.dispatch(e) for e in entries)

    def __len__(self) -> int:  # number of registered routes
        return len(self._routes)
