import corpus_graph_builder

from pathlib import Path


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
        "owners: [pipeline-team]\n"
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
        f"Synthetic fixture component {slug} for graph building.\n"
    )


def _build_corpus(repo_root: Path) -> None:
    # Capabilities
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
        "The first capability.\n",
    )
    _write(
        repo_root / "specs" / "product" / "two.md",
        "---\n"
        "id: P-TWO\n"
        "title: Capability Two\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# P-TWO\n"
        "\n"
        "The second capability.\n",
    )

    # Components (no relations)
    for slug in ("a", "b", "c"):
        _write(
            repo_root / "specs" / "components" / slug / "component.md",
            _component_md(slug),
        )

    # Requirement file for comp-a, with a matching acceptance criterion
    _write(
        repo_root / "specs" / "components" / "a" / "requirements" / "R-A-001.md",
        "# R-A-001\n"
        "\n"
        "**R-A-001** — The component MUST do the fixture thing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "a" / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a fixture input\n"
        "When the component runs\n"
        "Then it does the fixture thing\n"
        "```\n",
    )

    # Var
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
        "A fixture variable declaration.\n",
    )

    # Decision
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Decision One\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "A fixture decision.\n",
    )


def test_ac_graph_001_nodes_are_capabilities_components_and_vars(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    keys = set(nodes.keys()) if isinstance(nodes, dict) else set(nodes)

    expected = {"P-ONE", "P-TWO", "comp-a", "comp-b", "comp-c", "VAR-ONE"}
    assert keys == expected, f"unexpected node keys: {sorted(keys)}"

    # No requirement, criterion or decision nodes
    assert "R-A-001" not in keys
    assert "AC-A-001" not in keys
    assert "D1" not in keys

    expected_types = {
        "P-ONE": "capability",
        "P-TWO": "capability",
        "comp-a": "component",
        "comp-b": "component",
        "comp-c": "component",
        "VAR-ONE": "var",
    }
    for node_id, expected_type in expected_types.items():
        node = nodes[node_id]
        assert field(node, "type") == expected_type, (
            f"node {node_id} has type {field(node, 'type')!r}, "
            f"expected {expected_type!r}"
        )

    # build_corpus_graph writes nothing
    assert not (repo_root / "verification" / "corpus-graph.json").exists()