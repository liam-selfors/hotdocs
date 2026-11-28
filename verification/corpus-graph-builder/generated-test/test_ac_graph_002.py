# hotdocs-criterion: sha256:a3ba6ef83fdac873033070ab73dd466ea1240ec8d0e38dd47c96ad8568fccacd
"""AC-GRAPH-002: the graph holds one edge per depends_on, realizes and
uses_var relationship, sorted by from, to, kind (R-GRAPH-002)."""

from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def edge_as_dict(edge):
    if isinstance(edge, dict):
        return {"from": edge["from"], "to": edge["to"], "kind": edge["kind"]}
    if hasattr(edge, "to_dict"):
        d = edge.to_dict()
        return {"from": d["from"], "to": d["to"], "kind": d["kind"]}
    src = getattr(edge, "from", None)
    if src is None:
        src = getattr(edge, "from_", None)
    return {"from": src, "to": getattr(edge, "to"), "kind": getattr(edge, "kind")}


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "components" / "a" / "component.md",
        "---\n"
        + "id: comp-a\n"
        + "title: Component A\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: [comp-b]\n"
        + "realizes: [P-ONE]\n"
        + "uses_var: [VAR-ONE]\n"
        + "sealed: false\n"
        + "---\n"
        + "\n"
        + "# Component A\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Component A exists for a test.\n",
    )
    write(
        repo_root / "specs" / "components" / "b" / "component.md",
        "---\n"
        + "id: comp-b\n"
        + "title: Component B\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "realizes: []\n"
        + "uses_var: []\n"
        + "sealed: true\n"
        + "source_path: legacy/b/\n"
        + "---\n"
        + "\n"
        + "# Component B\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Component B exists for a test.\n",
    )
    write(
        repo_root / "specs" / "product" / "one.md",
        "---\n"
        + "id: P-ONE\n"
        + "title: Capability One\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# Capability One\n"
        + "\n"
        + "A capability for a test.\n",
    )
    write(
        repo_root / "specs" / "vars" / "VAR-ONE.md",
        "---\n"
        + "id: VAR-ONE\n"
        + "title: Var One\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# Var One\n"
        + "\n"
        + "A var for a test.\n",
    )


EXPECTED_EDGES = [
    {"from": "comp-a", "to": "P-ONE", "kind": "realizes"},
    {"from": "comp-a", "to": "VAR-ONE", "kind": "uses_var"},
    {"from": "comp-a", "to": "comp-b", "kind": "depends_on"},
]


def test_ac_graph_002_edges_exact_and_sorted(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    edges = [edge_as_dict(e) for e in field(graph, "edges")]
    assert edges == EXPECTED_EDGES

    # Sorted by from, then to, then kind.
    assert edges == sorted(edges, key=lambda e: (e["from"], e["to"], e["kind"]))

    # The serialized shape carries the same exact edge list.
    as_dict = graph.to_dict()
    assert [
        {"from": e["from"], "to": e["to"], "kind": e["kind"]}
        for e in as_dict["edges"]
    ] == EXPECTED_EDGES
    assert all(set(e.keys()) == {"from", "to", "kind"} for e in as_dict["edges"])

    # build_corpus_graph writes nothing.
    assert not (repo_root / "verification" / "corpus-graph.json").exists()