# hotdocs-criterion: sha256:0956680ec7bab927e2aa971afa72886a708bbaca38a5d19c0baa27cd5fdba433
import corpus_graph_builder

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_text(comp_id, title, depends_on, realizes, uses_var):
    return (
        "---\n"
        + "id: " + comp_id + "\n"
        + "title: " + title + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: [" + ", ".join(depends_on) + "]\n"
        + "realizes: [" + ", ".join(realizes) + "]\n"
        + "uses_var: [" + ", ".join(uses_var) + "]\n"
        + "sealed: false\n"
        + "---\n"
        + "\n"
        + "# " + title + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A fixture component.\n"
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "components" / "a" / "component.md",
        component_text("comp-a", "Component A", ["comp-b"], ["P-ONE"], ["VAR-ONE"]),
    )
    write(
        repo_root / "specs" / "components" / "b" / "component.md",
        component_text("comp-b", "Component B", [], [], []),
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
        + "# Capability One\n",
    )
    write(
        repo_root / "specs" / "vars" / "one.md",
        "---\n"
        + "id: VAR-ONE\n"
        + "title: Var One\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# Var One\n",
    )


def normalize_edge(edge):
    return {
        "from": field(edge, "from"),
        "to": field(edge, "to"),
        "kind": field(edge, "kind"),
    }


def test_ac_graph_002_edges_one_per_relationship_sorted(tmp_path):
    repo_root = Path(tmp_path)
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