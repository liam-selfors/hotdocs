# hotdocs-criterion: sha256:c34333e39c3318f828dbdaac7500ca85e9d3d0e72fecae44dc06f4153a57e9cb
"""AC-GRAPH-011 (covers R-GRAPH-003): a component node carries its owners
and documents exactly as interface/data/CorpusGraph.md defines them."""

from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


COMPONENT_MD = (
    "---\n"
    "id: comp-a\n"
    "title: Component A\n"
    "status: draft\n"
    "owners: [team-x]\n"
    "depends_on: []\n"
    "realizes: []\n"
    "uses_var: []\n"
    "sealed: true\n"
    "source_path: legacy/a/\n"
    "---\n"
    "\n"
    "# Component A\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A fixture component used to check owners and documents.\n"
)

REQUIREMENT_MD = (
    "# R-A-001\n"
    "\n"
    "**R-A-001** \u2014 Component A MUST do its one thing.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "do_thing() -> None\n"
    "```\n"
)


def test_ac_graph_011_owners_and_documents(tmp_path):
    repo_root = tmp_path / "repo"
    comp_dir = repo_root / "specs" / "components" / "a"
    _write(comp_dir / "component.md", COMPONENT_MD)
    _write(comp_dir / "requirements" / "R-A-001.md", REQUIREMENT_MD)
    _write(comp_dir / "interface" / "library.md", LIBRARY_MD)
    (repo_root / "specs" / "product").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "vars").mkdir(parents=True, exist_ok=True)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    assert "comp-a" in nodes
    node = nodes["comp-a"]

    assert list(field(node, "owners")) == ["team-x"]

    documents = field(node, "documents")
    assert sorted(documents.keys()) == [
        "component.md",
        "interface/library.md",
        "requirements/R-A-001.md",
    ]
    assert set(documents.keys()) == {
        "component.md",
        "interface/library.md",
        "requirements/R-A-001.md",
    }
    assert documents["component.md"] == COMPONENT_MD
    assert documents["interface/library.md"] == LIBRARY_MD
    assert documents["requirements/R-A-001.md"] == REQUIREMENT_MD

    # The serialized form carries the same owners and documents.
    as_dict = graph.to_dict()
    d_node = as_dict["nodes"]["comp-a"]
    assert d_node["owners"] == ["team-x"]
    assert d_node["documents"] == {
        "component.md": COMPONENT_MD,
        "interface/library.md": LIBRARY_MD,
        "requirements/R-A-001.md": REQUIREMENT_MD,
    }