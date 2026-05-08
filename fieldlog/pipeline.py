"""
pipeline.py — Convenience builder for composing fieldlog components
into a linear processing pipeline.

A Pipeline chains callables (filters, transformers, samplers, rate-limiters,
a batcher, etc.) and terminates at a sink.  Each stage receives an entry dict
and may drop it (by returning / raising) or pass it along.

Usage example::

    from fieldlog.pipeline import Pipeline
    from fieldlog.filter import Filter
    from fieldlog.transformer import Transformer
    from fieldlog.batcher import Batcher

    pipeline = (
        Pipeline()
        .add(Filter.by_level(min_level="WARNING"))
        .add(Transformer.add_fields(env="prod"))
        .batch(max_size=20, max_age_seconds=2.0)
        .build(sink=my_batch_sink)
    )

    pipeline(entry)  # route a single entry through the pipeline
"""

from typing import Any, Callable, List, Optional
from fieldlog.batcher import Batcher


class Pipeline:
    """Fluent builder that wires stages together into a single callable."""

    def __init__(self) -> None:
        self._stages: List[Callable[[dict], Optional[dict]]] = []
        self._batcher_kwargs: Optional[dict] = None

    # ------------------------------------------------------------------
    # Builder methods
    # ------------------------------------------------------------------

    def add(self, stage: Callable[[dict], Any]) -> "Pipeline":
        """Append a processing stage (filter, transformer, sampler …)."""
        self._stages.append(stage)
        return self

    def batch(
        self,
        *,
        max_size: int = 50,
        max_age_seconds: float = 5.0,
    ) -> "Pipeline":
        """Configure a Batcher as the final stage before the sink."""
        self._batcher_kwargs = {
            "max_size": max_size,
            "max_age_seconds": max_age_seconds,
        }
        return self

    def build(
        self,
        sink: Callable,
    ) -> "_BuiltPipeline":
        """Materialise the pipeline and return a callable."""
        if self._batcher_kwargs is not None:
            terminal: Callable = Batcher(sink, **self._batcher_kwargs)
        else:
            terminal = sink

        return _BuiltPipeline(list(self._stages), terminal)


class _BuiltPipeline:
    """The compiled, callable pipeline produced by Pipeline.build()."""

    def __init__(
        self,
        stages: List[Callable],
        terminal: Callable,
    ) -> None:
        self._stages = stages
        self._terminal = terminal

    def __call__(self, entry: dict) -> None:
        current = entry
        for stage in self._stages:
            result = stage(current)
            # A stage that returns a falsy value (None / False) drops the entry
            if result is None or result is False:
                return
            if isinstance(result, dict):
                current = result
            # If stage returns True (e.g. a filter that passed), keep current
        self._terminal(current)

    def flush(self) -> None:
        """Flush the terminal batcher if one is configured."""
        if isinstance(self._terminal, Batcher):
            self._terminal.flush()
