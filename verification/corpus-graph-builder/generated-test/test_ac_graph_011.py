# hotdocs-criterion: sha256:6b2df5e2d9f8d8a9a61bdd69efa127079f2882316259c8303144ce4dfdc50dbb
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
    "---\n"
    "id: comp-a\n"
    "title: Component A\n"
    "status: draft\n"
    "owners: [team-x]\n"
    "sealed: true\n"
    "source_path: legacy/a/\n"
    "depends_on: []\n"
    "realizes: []\n"
    "uses_var: []\n"
    "---\n"
    "\n"
    "# comp-a\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A fixture component used to check owners and documents.\n"
)

REQUIREMENT_MD = (
    "# R-A-001\n"
    "\n"
    "**R-A-001** \u2014 Component A MUST do one thing.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "do_thing() -> None\n"
    "```\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def test_component_node_carries_owners_and_documents(tmp_path):
    repo_root = tmp_path
    comp_dir = repo_root / "specs" / "components" / "a"
    _write(comp_dir / "component.md", COMPONENT_MD)
    _write(comp_dir / "requirements" / "R-A-001.md", REQUIREMENT_MD)
    _write(comp_dir / "interface" / "library.md", LIBRARY_MD)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    assert "comp-a" in nodes
    node = nodes["comp-a"]

    owners = field(node, "owners")
    assert list(owners) == ["team-x"]

    documents = field(node, "documents")
    documents = dict(documents)
    assert set(documents.keys()) == {
        "component.md",
        "interface/library.md",
        "requirements/R-A-001.md",
    }
    assert documents["component.md"] == COMPONENT_MD
    assert documents["interface/library.md"] == LIBRARY_MD
    assert documents["requirements/R-A-001.md"] == REQUIREMENT_MD

    # The serialized shape agrees as well.
    as_dict = graph.to_dict()
    node_dict = as_dict["nodes"]["comp-a"]
    assert node_dict["owners"] == ["team-x"]
    assert sorted(node_dict["documents"].keys()) == [
        "component.md",
        "interface/library.md",
        "requirements/R-A-001.md",
    ]
    assert node_dict["documents"]["component.md"] == COMPONENT_MD
    assert node_dict["documents"]["interface/library.md"] == LIBRARY_MD
    assert node_dict["documents"]["requirements/R-A-001.md"] == REQUIREMENT_MD