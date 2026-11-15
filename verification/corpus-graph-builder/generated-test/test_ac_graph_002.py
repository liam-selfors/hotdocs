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
        "# Component A\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Component A exists to exercise graph edges.\n",
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
        "# Component B\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Component B is depended upon by component A.\n",
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
        "# Capability One\n"
        "\n"
        "A capability realized by component A.\n",
    )
    _write(
        repo_root / "specs" / "vars" / "VAR-ONE.md",
        "---\n"
        "id: VAR-ONE\n"
        "title: Var One\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# VAR-ONE\n"
        "\n"
        "A var used by component A.\n",
    )


def _edge_to_dict(edge):
    return {
        "from": field(edge, "from"),
        "to": field(edge, "to"),
        "kind": field(edge, "kind"),
    }


def test_edges_one_per_declared_relationship_sorted(tmp_path):
    repo_root = Path(tmp_path)
    _build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    edges = [_edge_to_dict(e) for e in list(field(graph, "edges"))]

    expected = [
        {"from": "comp-a", "to": "P-ONE", "kind": "realizes"},
        {"from": "comp-a", "to": "VAR-ONE", "kind": "uses_var"},
        {"from": "comp-a", "to": "comp-b", "kind": "depends_on"},
    ]

    assert edges == expected

    # Sorted by from, then to, then kind.
    keys = [(e["from"], e["to"], e["kind"]) for e in edges]
    assert keys == sorted(keys)

    # The serialized form carries exactly the same edges.
    as_dict = graph.to_dict()
    assert [_edge_to_dict(e) for e in as_dict["edges"]] == expected