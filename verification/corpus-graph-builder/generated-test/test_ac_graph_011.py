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
    "A small fixture component used to check graph node documents.\n"
)

REQUIREMENT_MD = (
    "# R-A-001\n"
    "\n"
    "**R-A-001** — Component A MUST do its one thing.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "do_a_thing(x: int) -> int\n"
    "```\n"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_component_node_carries_owners_and_documents(tmp_path):
    repo_root = tmp_path / "repo"
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
    assert documents["component.md"] == (comp_dir / "component.md").read_text(
        encoding="utf-8"
    )
    assert documents["component.md"] == COMPONENT_MD
    assert documents["interface/library.md"] == LIBRARY_MD
    assert documents["requirements/R-A-001.md"] == REQUIREMENT_MD

    # build_corpus_graph writes nothing
    assert not (repo_root / "verification" / "corpus-graph.json").exists()