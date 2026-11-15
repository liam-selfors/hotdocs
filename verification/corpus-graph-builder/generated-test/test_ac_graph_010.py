import sys
from pathlib import Path

import pytest

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = """---
id: comp-a
title: Component A
status: draft
owners: [test-team]
depends_on: []
realizes: []
uses_var: []
sealed: true
source_path: legacy/a/
---

# Component A

## Purpose

A synthetic component used to check that the graph builder loads its
query engine by file path.
"""


def _write_corpus(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "a"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")


def test_build_corpus_graph_loads_query_engine_by_file_path(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_corpus(repo_root)
    assert not (repo_root / "gen").exists()

    # Strip every sys.path entry naming graph-query-engine, so a bare
    # `import graph_query_engine` could not succeed.
    stripped = [
        entry
        for entry in sys.path
        if "graph-query-engine" not in str(entry)
    ]
    monkeypatch.setattr(sys, "path", stripped)
    monkeypatch.delitem(sys.modules, "graph_query_engine", raising=False)

    assert not any("graph-query-engine" in str(entry) for entry in sys.path)
    assert "graph_query_engine" not in sys.modules

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    assert "comp-a" in nodes