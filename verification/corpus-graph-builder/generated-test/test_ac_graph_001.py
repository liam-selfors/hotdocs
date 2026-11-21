# hotdocs-criterion: sha256:c1c769e48caffb78f4ecf351be1712fdbe54148f2e6d7c969e94e02056e4f9ba
"""AC-GRAPH-001: the graph holds one node per capability, component and var."""

import corpus_graph_builder

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def capability_doc(cap_id, title):
    return (
        "---\n"
        + "id: " + cap_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "A test capability.\n"
    )


def component_doc(slug):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: Component " + slug + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "realizes: []\n"
        + "uses_var: []\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# Component " + slug + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A test component.\n"
    )


def var_doc(var_id, title):
    return (
        "---\n"
        + "id: " + var_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "A test var.\n"
    )


def decision_doc():
    return (
        "---\n"
        + "id: D1\n"
        + "title: Decision one\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# Decision one\n"
        + "\n"
        + "A test decision.\n"
    )


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(specs / "product" / "one.md", capability_doc("P-ONE", "Product one"))
    write(specs / "product" / "two.md", capability_doc("P-TWO", "Product two"))
    for slug in ("a", "b", "c"):
        write(specs / "components" / slug / "component.md", component_doc(slug))
    write(specs / "vars" / "one.md", var_doc("VAR-ONE", "Var one"))
    write(specs / "decisions" / "D1.md", decision_doc())
    write(
        specs / "components" / "a" / "requirements" / "R-A-001.md",
        "# R-A-001\n\n**R-A-001** \u2014 Component a MUST do something.\n",
    )
    write(
        specs / "components" / "a" / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n\nCovers: R-A-001\nKind: llm-judge\n\nComponent a does something.\n",
    )


def test_nodes_hold_exactly_capabilities_components_and_vars(tmp_path):
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

    # Requirements, criteria and decisions never become nodes.
    assert "R-A-001" not in nodes
    assert "AC-A-001" not in nodes
    assert "D1" not in nodes

    # build_corpus_graph writes nothing.
    assert not (repo_root / "verification" / "corpus-graph.json").exists()