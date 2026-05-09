"""
pipeline_extras: convenience helpers that attach Throttle (and other
stateful middleware) to a Pipeline in a fluent style, mirroring the
existing Pipeline.filter / .transform / .sample interface.
"""

from __future__ import annotations

from typing import Callable, Optional

from fieldlog.throttle import Throttle


class ThrottleStage:
    """
    A pipeline stage that wraps Throttle.

    Designed to slot into the fieldlog.pipeline.Pipeline._wrap chain:
    it accepts an entry dict and passes it to the next sink when allowed.
    """

    def __init__(
        self,
        limit: int,
        window: float,
        key_fn: Optional[Callable] = None,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._limit = limit
        self._window = window
        self._key_fn = key_fn
        self._clock = clock
        self._throttle: Optional[Throttle] = None

    def bind(self, next_sink: Callable) -> Callable:
        """Bind the stage to a downstream sink and return the callable."""
        kwargs = {}
        if self._key_fn is not None:
            kwargs["key_fn"] = self._key_fn
        if self._clock is not None:
            kwargs["clock"] = self._clock
        self._throttle = Throttle(
            limit=self._limit,
            window=self._window,
            sink=next_sink,
            **kwargs,
        )
        return self._throttle

    @property
    def dropped_count(self) -> int:
        if self._throttle is None:
            return 0
        return self._throttle.dropped_count()


def throttle_pipeline(
    pipeline,  # fieldlog.pipeline.Pipeline instance
    limit: int,
    window: float,
    key_fn: Optional[Callable] = None,
) -> "ThrottlePipelineView":
    """
    Attach a ThrottleStage to *pipeline* and return a view that exposes
    ``dropped_count`` alongside the original pipeline.

    Usage::

        from fieldlog.pipeline import Pipeline
        from fieldlog.pipeline_extras import throttle_pipeline

        p = Pipeline().filter(by_level("info")).sink(my_sink)
        tp = throttle_pipeline(p, limit=5, window=60)
        tp.process(entry)
        print(tp.dropped_count)
    """
    stage = ThrottleStage(limit=limit, window=window, key_fn=key_fn)
    return ThrottlePipelineView(pipeline, stage)


class ThrottlePipelineView:
    """Thin wrapper that adds throttle introspection to a Pipeline."""

    def __init__(self, pipeline, stage: ThrottleStage) -> None:
        self._pipeline = pipeline
        self._stage = stage
        # Wrap the pipeline's sink with the throttle stage
        original_sink = pipeline._sink  # type: ignore[attr-defined]
        self._throttle_sink = stage.bind(original_sink)

    def process(self, entry: dict) -> None:
        """Run the pipeline's pre-sink steps then apply throttle."""
        # Delegate filter/transform chain but redirect final call to throttle
        self._pipeline._sink = self._throttle_sink  # type: ignore[attr-defined]
        self._pipeline.process(entry)

    @property
    def dropped_count(self) -> int:
        return self._stage.dropped_count
