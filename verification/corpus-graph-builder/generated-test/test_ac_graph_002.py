from pathlib import Path

import pytest

import corpus_graph_builder


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _field(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"

    _write(
        root / "specs" / "components" / "a" / "component.md",
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: [comp-b]\n"
        "realizes: [P-ONE]\n"
        "uses_var: [VAR-ONE]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Component A for AC-GRAPH-002.\n",
    )

    _write(
        root / "specs" / "components" / "b" / "component.md",
        "---\n"
        "id: comp-b\n"
        "title: Component B\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Component B for AC-GRAPH-002.\n",
    )

    _write(
        root / "specs" / "product" / "one.md",
        "---\n"
        "id: P-ONE\n"
        "title: Capability One\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "Capability One description.\n",
    )

    _write(
        root / "specs" / "vars" / "one.md",
        "---\n"
        "id: VAR-ONE\n"
        "title: Var One\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "Var One description.\n",
    )

    return root


def test_edges_exact_for_three_relationship_kinds(repo_root):
    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    edges = _field(graph, "edges")

    actual = [
        {
            "from": _field(edge, "from"),
            "to": _field(edge, "to"),
            "kind": _field(edge, "kind"),
        }
        for edge in edges
    ]

    expected = [
        {"from": "comp-a", "to": "P-ONE", "kind": "realizes"},
        {"from": "comp-a", "to": "VAR-ONE", "kind": "uses_var"},
        {"from": "comp-a", "to": "comp-b", "kind": "depends_on"},
    ]

    assert actual == expected