"""CorpusGraph loading/normalization for the docs site renderer.

This is this component's *one and only* data source (R-DOCS-004): the file
at ``<repo_root>/verification/corpus-graph.json``, written by
`comp-corpus-graph-builder`. Per that dependency's
``interface/data/CorpusGraph.md``:

    {
      "nodes": {"<id>": {"type": "capability" | "component" | "var", ...}},
      "edges": [{"from": "...", "to": "...", "kind": "depends_on" | "realizes" | "uses_var"}],
      "aggregates": {"...": 0.0}
    }

We never call `comp-corpus-graph-builder`'s `build_corpus_graph` ourselves
(that would be a second computation step this component is explicitly out
of scope for) -- we only ever read its already-written JSON output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Union

CORPUS_GRAPH_RELATIVE_PATH = Path("verification") / "corpus-graph.json"


@dataclass
class CorpusGraph:
    """Local mirror of `interface/data/CorpusGraph.md`'s `{nodes, edges,
    aggregates}` shape.

    This component never constructs a `CorpusGraph` from scratch -- it only
    reads one already produced by `comp-corpus-graph-builder` and writes a
    rendered site from it (R-DOCS-004). This type exists so
    `render_docs_site`'s signature matches `interface/library.md`'s
    `render_docs_site(graph: CorpusGraph, out_dir: Path) -> None` exactly;
    any object exposing the same three attributes -- including the real
    `corpus_graph_builder.CorpusGraph` dataclass -- works equally well,
    since only attribute/key access is used, never `isinstance`.
    """

    nodes: "dict[str, dict[str, Any]]"
    edges: "list[dict[str, str]]"
    aggregates: "dict[str, float]"


GraphLike = Union[CorpusGraph, Mapping[str, Any]]


class CorpusGraphReadError(Exception):
    """Raised when `verification/corpus-graph.json` is missing or unreadable."""


def _as_mapping(obj: Any) -> Mapping[str, Any]:
    if isinstance(obj, Mapping):
        return obj
    # A dataclass (ours, or the real corpus_graph_builder.CorpusGraph, or
    # anything else shaped the same way) -- pull its three known attributes
    # defensively rather than requiring a specific class identity.
    return {
        "nodes": getattr(obj, "nodes", {}),
        "edges": getattr(obj, "edges", []),
        "aggregates": getattr(obj, "aggregates", {}),
    }


def coerce_graph(graph: GraphLike) -> CorpusGraph:
    """Normalizes any CorpusGraph-shaped value (plain dict loaded from JSON,
    our own `CorpusGraph`, or the dependency's `CorpusGraph` dataclass) into
    our local `CorpusGraph`."""
    m = _as_mapping(graph)
    return CorpusGraph(
        nodes=dict(m.get("nodes") or {}),
        edges=list(m.get("edges") or []),
        aggregates=dict(m.get("aggregates") or {}),
    )


def load_corpus_graph(repo_root: Path) -> CorpusGraph:
    """Reads `<repo_root>/verification/corpus-graph.json` -- this
    component's one and only data source (R-DOCS-004).

    Raises `CorpusGraphReadError` if the file is missing, unreadable, not
    valid JSON, or not a JSON object -- the CLI maps this to exit code 1.
    """
    path = Path(repo_root) / CORPUS_GRAPH_RELATIVE_PATH
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorpusGraphReadError(f"cannot read {path}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CorpusGraphReadError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CorpusGraphReadError(f"{path} does not contain a JSON object")
    return coerce_graph(data)