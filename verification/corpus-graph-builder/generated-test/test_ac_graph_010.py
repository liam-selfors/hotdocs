# hotdocs-criterion: sha256:00090bf306ccb963104d12878b2ed7ac65cd78290eac1a8ce87f82e9b3dcc552
import sys
from pathlib import Path

import pytest

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "a"
    write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/a/\n"
        "---\n"
        "\n"
        "# Component A\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component.\n",
    )
    write(
        comp_dir / "requirements" / "R-A-001.md",
        "**R-A-001** — Component A MUST exist.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: llm-judge\n"
        "\n"
        "Component A exists.\n",
    )
    write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "Nothing exported.\n",
    )
    write(
        comp_dir / "interface" / "guarantees" / "G-A-001.md",
        "**G-A-001** — Component A is stable.\n",
    )
    write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Capability X\n",
    )
    write(
        repo_root / "specs" / "vars" / "y.md",
        "---\n"
        "id: VAR-Y\n"
        "title: Var Y\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Var Y\n",
    )
    write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Decision One\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# D1\n",
    )


@pytest.fixture
def isolated_import_state():
    saved_path = list(sys.path)
    had_module = "graph_query_engine" in sys.modules
    saved_module = sys.modules.get("graph_query_engine")

    sys.path[:] = [p for p in sys.path if "graph-query-engine" not in str(p)]
    sys.modules.pop("graph_query_engine", None)
    try:
        yield
    finally:
        sys.path[:] = saved_path
        if had_module:
            sys.modules["graph_query_engine"] = saved_module
        else:
            sys.modules.pop("graph_query_engine", None)


def test_build_corpus_graph_loads_graph_query_engine_by_path(tmp_path, isolated_import_state):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    assert not (repo_root / "gen").exists()
    assert not any("graph-query-engine" in str(p) for p in sys.path)
    assert "graph_query_engine" not in sys.modules

    graph = corpus_graph_builder.build_corpus_graph(Path(repo_root))

    nodes = field(graph, "nodes")
    assert "comp-a" in nodes