from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug: str) -> str:
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: Component {slug.upper()}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        "\n"
        f"# comp-{slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Component {slug} exists only as a graph-builder test fixture.\n"
    )


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"

    # Capabilities
    _write(
        specs / "product" / "one.md",
        "---\n"
        "id: P-ONE\n"
        "title: Capability One\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# P-ONE\n"
        "\n"
        "The first capability.\n",
    )
    _write(
        specs / "product" / "two.md",
        "---\n"
        "id: P-TWO\n"
        "title: Capability Two\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# P-TWO\n"
        "\n"
        "The second capability.\n",
    )

    # Var
    _write(
        specs / "vars" / "VAR-ONE.md",
        "---\n"
        "id: VAR-ONE\n"
        "title: Var One\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# VAR-ONE\n"
        "\n"
        "A test variable declaration.\n",
    )

    # Decision
    _write(
        specs / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Decision One\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "A test decision.\n",
    )

    # Components (no relations)
    for slug in ("a", "b", "c"):
        _write(specs / "components" / slug / "component.md", _component_md(slug))

    # Requirement file (plus its matching acceptance criterion)
    _write(
        specs / "components" / "a" / "requirements" / "R-A-001.md",
        "**R-A-001** — Component a MUST exist as a fixture.\n",
    )
    _write(
        specs / "components" / "a" / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given component a\n"
        "When it is inspected\n"
        "Then it exists\n"
        "```\n",
    )


def test_ac_graph_001_nodes_are_exactly_capabilities_components_and_vars(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    expected_types = {
        "P-ONE": "capability",
        "P-TWO": "capability",
        "comp-a": "component",
        "comp-b": "component",
        "comp-c": "component",
        "VAR-ONE": "var",
    }

    assert set(nodes.keys()) == set(expected_types.keys()), (
        f"unexpected node keys: {sorted(nodes.keys())}"
    )

    for node_id, expected_type in expected_types.items():
        node = nodes[node_id]
        assert field(node, "type") == expected_type, (
            f"node {node_id} has type {field(node, 'type')!r}, "
            f"expected {expected_type!r}"
        )