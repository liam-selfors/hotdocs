"""Docs Site Renderer (comp-docs-site-renderer).

Pure presentation layer: renders ``verification/corpus-graph.json`` (the
`comp-corpus-graph-builder` output) into a static, interactive graph/docs
explorer site -- the DAG view, per-node detail view, and corpus-health
dashboard described in this component's SpecBundle (`component.md`,
`requirements/`, `interface/`, `constraints.md`).

This module performs no computation of its own beyond templating: it is a
pure function of the `CorpusGraph` it is handed (R-DOCS-004), makes no
model calls (R-DOCS-006), and its output is never committed -- it is a CI
build artifact (R-DOCS-005).
"""

from .graph import CorpusGraph, CorpusGraphReadError, coerce_graph, load_corpus_graph
from .renderer import render_docs_site
from .cli import main

__all__ = [
    "CorpusGraph",
    "CorpusGraphReadError",
    "coerce_graph",
    "load_corpus_graph",
    "render_docs_site",
    "main",
]