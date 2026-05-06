"""Log routing: dispatch entries to one or more sinks based on filter rules."""

from typing import Any, Callable, Dict, List, Optional

from fieldlog.filter import Filter


class Route:
    """Associates a :class:`Filter` with a sink callable."""

    def __init__(
        self,
        filt: Filter,
        sink: Callable[[Dict[str, Any]], None],
        *,
        label: Optional[str] = None,
    ) -> None:
        self.filt = filt
        self.sink = sink
        self.label = label

    def process(self, entry: Dict[str, Any]) -> bool:
        """Forward *entry* to sink if filter matches.  Returns match result."""
        if self.filt(entry):
            self.sink(entry)
            return True
        return False


class LogRouter:
    """Dispatches log entries to registered routes.

    Two strategies are supported:

    * **fanout** (default) – every matching route receives the entry.
    * **first-match** – only the first matching route receives the entry.
    """

    def __init__(self, *, first_match: bool = False) -> None:
        self._routes: List[Route] = []
        self.first_match = first_match

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_route(
        self,
        filt: Filter,
        sink: Callable[[Dict[str, Any]], None],
        *,
        label: Optional[str] = None,
    ) -> "LogRouter":
        """Register a new route and return *self* for chaining."""
        self._routes.append(Route(filt, sink, label=label))
        return self

    def dispatch(self, entry: Dict[str, Any]) -> int:
        """Send *entry* through all (or first matching) routes.

        Returns the number of sinks that received the entry.
        """
        hits = 0
        for route in self._routes:
            matched = route.process(entry)
            if matched:
                hits += 1
                if self.first_match:
                    break
        return hits

    def __len__(self) -> int:  # pragma: no cover
        return len(self._routes)
