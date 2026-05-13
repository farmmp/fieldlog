"""
fieldlog.pipeline_splitter
~~~~~~~~~~~~~~~~~~~~~~~~~~
Convenience helpers that integrate :class:`~fieldlog.splitter.Splitter`
with the :class:`~fieldlog.pipeline.Pipeline` API so callers can add a
split stage fluently.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from fieldlog.pipeline import Pipeline
from fieldlog.splitter import Splitter


def splitter_stage(
    key_fn: Callable[[Dict[str, Any]], str],
    sinks: Dict[str, Callable[[Dict[str, Any]], None]],
    default_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Splitter:
    """Create a :class:`Splitter` suitable for use as a pipeline sink.

    The returned object is callable and can be passed directly to
    :meth:`Pipeline.sink` or used standalone.

    Example::

        from fieldlog.pipeline import Pipeline
        from fieldlog.pipeline_splitter import splitter_stage

        info_writer  = ...  # some sink
        error_writer = ...  # some sink

        sp = splitter_stage(
            key_fn=lambda e: e["level"],
            sinks={"info": info_writer, "error": error_writer},
        )

        pipeline = (
            Pipeline()
            .filter(lambda e: "level" in e)
            .sink(sp)
        )
    """
    return Splitter(key_fn=key_fn, sinks=sinks, default_sink=default_sink)


def split_pipeline(
    key_fn: Callable[[Dict[str, Any]], str],
    sinks: Dict[str, Callable[[Dict[str, Any]], None]],
    default_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    *,
    base_pipeline: Optional[Pipeline] = None,
) -> Pipeline:
    """Build a :class:`~fieldlog.pipeline.Pipeline` whose terminal stage is
    a :class:`Splitter`.

    Parameters
    ----------
    key_fn:
        Callable that extracts the routing key from an entry.
    sinks:
        Mapping of key -> sink callable.
    default_sink:
        Optional fallback for unmatched keys.
    base_pipeline:
        If given, the splitter is appended to this pipeline; otherwise a
        fresh :class:`Pipeline` is created.

    Returns
    -------
    Pipeline
        A pipeline whose final stage dispatches entries via the splitter.
    """
    sp = Splitter(key_fn=key_fn, sinks=sinks, default_sink=default_sink)
    pipeline = base_pipeline if base_pipeline is not None else Pipeline()
    return pipeline.sink(sp)
