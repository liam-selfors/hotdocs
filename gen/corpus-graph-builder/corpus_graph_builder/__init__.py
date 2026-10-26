"""corpus_graph_builder — builds `verification/corpus-graph.json`.

Public surface mirrors `interface/library.md`:

    build_corpus_graph(repo_root: Path) -> CorpusGraph

See `builder.py` for the implementation and `cli.py` for the
`hotdocs corpus-graph build` command.
"""

from __future__ import annotations

from .builder import CorpusGraph, build_corpus_graph, write_corpus_graph

__all__ = ["CorpusGraph", "build_corpus_graph", "write_corpus_graph"]
