"""Fluent pipeline builder for fieldlog."""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

from fieldlog.batcher import Batcher
from fieldlog.filter import Filter
from fieldlog.sampler import Sampler
from fieldlog.schema import Schema
from fieldlog.transformer import Transformer
from fieldlog.validating_sink import ValidatingSink


class Pipeline:
    """Builds a chain of log-processing steps that feed into a terminal sink.

    Usage::

        sink = Pipeline(terminal_sink)\
            .validate()\
            .filter(Filter.by_level(min_level="info"))\
            .transform(Transformer.add_fields(env="prod"))\
            .build()
    """

    def __init__(self, terminal: Callable[[Dict[str, Any]], None]) -> None:
        if not callable(terminal):
            raise TypeError("terminal must be callable")
        self._terminal = terminal
        self._steps: List[Callable[[Callable], Callable]] = []

    # ------------------------------------------------------------------
    def validate(
        self,
        schema: Optional[Schema] = None,
        on_error: Optional[Callable] = None,
    ) -> "Pipeline":
        """Add a :class:`ValidatingSink` step."""
        def _wrap(nxt):
            return ValidatingSink(nxt, schema=schema, on_error=on_error)
        self._steps.append(_wrap)
        return self

    def filter(self, predicate: Filter) -> "Pipeline":
        """Add a :class:`Filter` step."""
        def _wrap(nxt):
            def _step(entry):
                if predicate(entry):
                    nxt(entry)
            return _step
        self._steps.append(_wrap)
        return self

    def transform(self, transformer: Transformer) -> "Pipeline":
        """Add a :class:`Transformer` step."""
        def _wrap(nxt):
            def _step(entry):
                nxt(transformer(entry))
            return _step
        self._steps.append(_wrap)
        return self

    def sample(self, rate: float) -> "Pipeline":
        """Add a :class:`Sampler` step."""
        def _wrap(nxt):
            return Sampler(rate, sink=nxt)
        self._steps.append(_wrap)
        return self

    def batch(
        self,
        max_size: int = 50,
        max_age: float = 5.0,
        flush_sink: Optional[Callable[[Iterable[Dict[str, Any]]], None]] = None,
    ) -> "Pipeline":
        """Add a :class:`Batcher` step."""
        def _wrap(nxt):
            def _batch_sink(entries):
                for e in entries:
                    nxt(e)
            return Batcher(flush_sink or _batch_sink, max_size=max_size, max_age=max_age)
        self._steps.append(_wrap)
        return self

    def add(self, wrapper: Callable[[Callable], Callable]) -> "Pipeline":
        """Add an arbitrary step factory."""
        self._steps.append(wrapper)
        return self

    def build(self) -> Callable[[Dict[str, Any]], None]:
        """Assemble and return the callable pipeline."""
        current: Callable = self._terminal
        for wrap in reversed(self._steps):
            current = wrap(current)
        return current
