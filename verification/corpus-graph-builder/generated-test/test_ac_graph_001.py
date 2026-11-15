import corpus_graph_builder

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root: Path, slug: str) -> None:
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
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
        f"# Component {slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"A synthetic test component named {slug}.\n",
    )


def _capability(repo_root: Path, name: str, cap_id: str) -> None:
    _write(
        repo_root / "specs" / "product" / f"{name}.md",
        "---\n"
        f"id: {cap_id}\n"
        f"title: Capability {name}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        f"# Capability {name}\n"
        "\n"
        "A synthetic capability.\n",
    )


def _build_corpus(repo_root: Path) -> None:
    _capability(repo_root, "one", "P-ONE")
    _capability(repo_root, "two", "P-TWO")

    for slug in ("a", "b", "c"):
        _component(repo_root, slug)

    _write(
        repo_root / "specs" / "vars" / "VAR-ONE.md",
        "---\n"
        "id: VAR-ONE\n"
        "title: Var one\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# VAR-ONE\n"
        "\n"
        "A synthetic var declaration.\n",
    )

    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Decision one\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "A synthetic decision.\n",
    )

    _write(
        repo_root / "specs" / "components" / "a" / "requirements" / "R-A-001.md",
        "**R-A-001** — Component a MUST do its one thing.\n",
    )
    _write(
        repo_root / "specs" / "components" / "a" / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given component a\n"
        "When it runs\n"
        "Then it does its one thing\n"
        "```\n",
    )


def test_ac_graph_001_nodes_are_capabilities_components_and_vars(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    keys = set(nodes.keys())
    assert keys == {"P-ONE", "P-TWO", "comp-a", "comp-b", "comp-c", "VAR-ONE"}, keys
    assert len(nodes) == 6

    expected_types = {
        "P-ONE": "capability",
        "P-TWO": "capability",
        "comp-a": "component",
        "comp-b": "component",
        "comp-c": "component",
        "VAR-ONE": "var",
    }
    for node_id, expected_type in expected_types.items():
        assert field(nodes[node_id], "type") == expected_type, (
            node_id,
            field(nodes[node_id], "type"),
        )

    # Requirements, criteria and decisions never appear as nodes.
    for excluded in ("D1", "R-A-001", "AC-A-001"):
        assert excluded not in nodes