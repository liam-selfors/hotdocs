import corpus_graph_builder

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "components" / "a" / "component.md",
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: [comp-b]\n"
        "realizes: [P-ONE]\n"
        "uses_var: [VAR-ONE]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# comp-a\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Component A exists for graph edge testing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "b" / "component.md",
        "---\n"
        "id: comp-b\n"
        "title: Component B\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/b/\n"
        "---\n"
        "\n"
        "# comp-b\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Component B is a dependency target.\n",
    )
    _write(
        repo_root / "specs" / "product" / "one.md",
        "---\n"
        "id: P-ONE\n"
        "title: Capability One\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# P-ONE\n"
        "\n"
        "A capability.\n",
    )
    _write(
        repo_root / "specs" / "vars" / "one.md",
        "---\n"
        "id: VAR-ONE\n"
        "title: Var One\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# VAR-ONE\n"
        "\n"
        "A var.\n",
    )


def _normalize_edges(edges):
    return [
        {"from": field(e, "from"), "to": field(e, "to"), "kind": field(e, "kind")}
        for e in edges
    ]


def test_ac_graph_002_edges_exactly_declared_relationships(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    expected = [
        {"from": "comp-a", "to": "P-ONE", "kind": "realizes"},
        {"from": "comp-a", "to": "VAR-ONE", "kind": "uses_var"},
        {"from": "comp-a", "to": "comp-b", "kind": "depends_on"},
    ]

    edges = _normalize_edges(list(field(graph, "edges")))
    assert edges == expected

    # Sorted by from, then to, then kind.
    assert edges == sorted(edges, key=lambda e: (e["from"], e["to"], e["kind"]))

    # The serialized form carries the same edges.
    as_dict = graph.to_dict()
    assert _normalize_edges(list(as_dict["edges"])) == expected