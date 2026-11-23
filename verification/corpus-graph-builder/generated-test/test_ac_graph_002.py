# hotdocs-criterion: sha256:9bfe3940f46125b1e5348ccc7527c84407df07eb1cc597d15131a0bb7ea40d00
import corpus_graph_builder

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(
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
        "Component A does a thing.\n",
    )
    write(
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
        "Component B does another thing.\n",
    )
    write(
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
        "A capability.\n",
    )
    write(
        repo_root / "specs" / "vars" / "one.md",
        "---\n"
        "id: VAR-ONE\n"
        "title: Var One\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Var One\n"
        "\n"
        "A var.\n",
    )


def normalize_edge(edge):
    return {
        "from": field(edge, "from"),
        "to": field(edge, "to"),
        "kind": field(edge, "kind"),
    }


def test_ac_graph_002_edges_one_per_relationship_sorted(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    edges = [normalize_edge(e) for e in field(graph, "edges")]

    expected = [
        {"from": "comp-a", "to": "P-ONE", "kind": "realizes"},
        {"from": "comp-a", "to": "VAR-ONE", "kind": "uses_var"},
        {"from": "comp-a", "to": "comp-b", "kind": "depends_on"},
    ]

    assert edges == expected
    assert edges == sorted(edges, key=lambda e: (e["from"], e["to"], e["kind"]))

    as_dict = graph.to_dict()
    dict_edges = [normalize_edge(e) for e in as_dict["edges"]]
    assert dict_edges == expected