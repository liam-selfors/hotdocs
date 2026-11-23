# hotdocs-criterion: sha256:a1749ebee997de79a38ebee662de469e1abea68b77f30319d2a3b172b94dd5ac
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: Component " + slug.upper() + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# Component " + slug.upper() + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component named " + slug + ".\n"
    )


def capability_md(cap_id, title):
    return (
        "---\n"
        "id: " + cap_id + "\n"
        "title: " + title + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# " + title + "\n"
        "\n"
        "A fixture capability.\n"
    )


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(specs / "product" / "one.md", capability_md("P-ONE", "Capability One"))
    write(specs / "product" / "two.md", capability_md("P-TWO", "Capability Two"))

    for slug in ("a", "b", "c"):
        write(specs / "components" / slug / "component.md", component_md(slug))

    write(
        specs / "components" / "a" / "requirements" / "R-A-001.md",
        "# R-A-001\n\n**R-A-001** \u2014 Component a MUST do its job.\n",
    )
    write(
        specs / "components" / "a" / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given component a\n"
        "When it runs\n"
        "Then it does its job\n"
        "```\n",
    )

    write(
        specs / "vars" / "one.md",
        "---\n"
        "id: VAR-ONE\n"
        "title: Var One\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# VAR-ONE\n"
        "\n"
        "A fixture var declaration.\n",
    )

    write(
        specs / "decisions" / "D1.md",
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
    build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    nodes = field(graph, "nodes")

    expected = {
        "P-ONE": "capability",
        "P-TWO": "capability",
        "comp-a": "component",
        "comp-b": "component",
        "comp-c": "component",
        "VAR-ONE": "var",
    }

    assert set(nodes.keys()) == set(expected.keys())
    for node_id, node_type in expected.items():
        assert field(nodes[node_id], "type") == node_type, node_id