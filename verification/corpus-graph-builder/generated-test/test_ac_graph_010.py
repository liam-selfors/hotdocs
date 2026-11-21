# hotdocs-criterion: sha256:13d017bc2962e352e2e9bce8a353012e5664d3b4a2019c15028c5754d30480f2
import sys
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    component_md = (
        "---\n"
        + "id: comp-a\n"
        + "title: Component A\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "realizes: []\n"
        + "uses_var: []\n"
        + "sealed: true\n"
        + "source_path: legacy/a/\n"
        + "---\n"
        + "\n"
        + "# Component A\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A tiny fixture component used to build a corpus graph.\n"
    )
    _write(repo_root / "specs" / "components" / "a" / "component.md", component_md)


def test_ac_graph_010_loads_graph_query_engine_by_path(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    assert not (repo_root / "gen").exists()

    cleaned_path = [p for p in sys.path if "graph-query-engine" not in str(p)]
    monkeypatch.setattr(sys, "path", cleaned_path)
    monkeypatch.delitem(sys.modules, "graph_query_engine", raising=False)

    assert not any("graph-query-engine" in str(p) for p in sys.path)
    assert "graph_query_engine" not in sys.modules

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    if isinstance(nodes, dict):
        node_ids = set(nodes.keys())
    else:
        node_ids = set()
        for node in nodes:
            node_ids.add(field(node, "id"))
    assert "comp-a" in node_ids