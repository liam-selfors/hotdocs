"""AC-GRAPH-010: build_corpus_graph loads graph-query-engine by file path.

Given a repo_root holding comp-a and no gen/ directory, with every sys.path
entry that names graph-query-engine removed and graph_query_engine popped
from sys.modules for the test, when build_corpus_graph(repo_root) runs, then
it returns a graph whose nodes include comp-a.
"""

import sys
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "a"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "uses_var: [VAR-Y]\n"
        "sealed: true\n"
        "source_path: legacy/a/\n"
        "---\n"
        "\n"
        "# Component A\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used to exercise graph building.\n",
    )
    _write(
        comp_dir / "requirements" / "R-A-001.md",
        "# R-A-001\n"
        "\n"
        "**R-A-001** — Component A MUST exist.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a component A\n"
        "When it is inspected\n"
        "Then it exists\n"
        "```\n",
    )
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Capability X\n",
    )
    _write(
        repo_root / "specs" / "vars" / "y.md",
        "---\n"
        "id: VAR-Y\n"
        "title: Var Y\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Var Y\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Decision one\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# D1\n",
    )


def _names_gqe(entry) -> bool:
    text = str(entry)
    return "graph-query-engine" in text or "graph_query_engine" in text


def test_build_corpus_graph_loads_gqe_by_file_path_without_sys_path(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    assert not (repo_root / "gen").exists()

    # Remove every sys.path entry naming graph-query-engine, and make sure no
    # already-imported graph_query_engine module can be reused by name.
    monkeypatch.setattr(sys, "path", [p for p in sys.path if not _names_gqe(p)])
    monkeypatch.delitem(sys.modules, "graph_query_engine", raising=False)
    assert not any(_names_gqe(p) for p in sys.path)
    assert "graph_query_engine" not in sys.modules

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    assert "comp-a" in nodes, f"comp-a missing from nodes: {sorted(nodes)!r}"

    # build_corpus_graph writes nothing.
    assert not (repo_root / "gen").exists()
    assert not (repo_root / "verification" / "corpus-graph.json").exists()