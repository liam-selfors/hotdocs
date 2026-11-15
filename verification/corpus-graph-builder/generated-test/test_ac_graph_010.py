import sys
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "components" / "a" / "component.md",
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/a/\n"
        "---\n"
        "# comp-a\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A synthetic component used to exercise the corpus graph builder.\n",
    )


def test_ac_graph_010_loads_graph_query_engine_by_path_without_sys_path(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _make_corpus(repo_root)

    # Precondition: no gen/ directory under repo_root.
    assert not (repo_root / "gen").exists()

    # Remove every sys.path entry naming graph-query-engine, and make sure
    # no previously imported graph_query_engine module is reachable by name.
    filtered = [p for p in sys.path if "graph-query-engine" not in str(p)]
    monkeypatch.setattr(sys, "path", filtered)
    monkeypatch.delitem(sys.modules, "graph_query_engine", raising=False)

    assert not any("graph-query-engine" in str(p) for p in sys.path)
    assert "graph_query_engine" not in sys.modules

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    if isinstance(nodes, dict):
        node_ids = set(nodes.keys())
    else:
        node_ids = set()
        for n in nodes:
            node_ids.add(n if isinstance(n, str) else field(n, "id"))
    assert "comp-a" in node_ids