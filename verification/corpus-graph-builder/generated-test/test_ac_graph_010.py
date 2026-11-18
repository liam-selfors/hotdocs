# hotdocs-criterion: sha256:9e69cf5fecf8c6836b1e674b9db91ff747a6c220cd7f6c735df0b685dfaf33c7
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
        + "owners: [team-a]\n"
        + "depends_on: []\n"
        + "realizes: []\n"
        + "uses_var: []\n"
        + "sealed: true\n"
        + "source_path: legacy/a/\n"
        + "---\n"
        + "\n"
        + "# comp-a\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A small fixture component.\n"
    )
    _write(repo_root / "specs" / "components" / "a" / "component.md", component_md)


def _names_gqe(entry):
    text = str(entry)
    return "graph-query-engine" in text or "graph_query_engine" in text


def test_build_corpus_graph_loads_gqe_without_sys_path(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    assert not (repo_root / "gen").exists()

    monkeypatch.setattr(sys, "path", [p for p in sys.path if not _names_gqe(p)])
    monkeypatch.delitem(sys.modules, "graph_query_engine", raising=False)

    assert not any(_names_gqe(p) for p in sys.path)
    assert "graph_query_engine" not in sys.modules

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    assert "comp-a" in nodes