# hotdocs-criterion: sha256:d11d97ccc57e7e78f644ad3a8e012e491fcea6f224f938968adf1f4bfd238e0b
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
    "Component A exists to test the corpus graph builder.\n"
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
    path.write_text(text, encoding="utf-8")


def test_ac_graph_011_component_node_owners_and_documents(tmp_path):
    repo_root = tmp_path
    comp_dir = repo_root / "specs" / "components" / "a"
    _write(comp_dir / "component.md", COMPONENT_MD)
    _write(comp_dir / "requirements" / "R-A-001.md", REQUIREMENT_MD)
    _write(comp_dir / "interface" / "library.md", LIBRARY_MD)

    graph = corpus_graph_builder.build_corpus_graph(Path(repo_root))

    nodes = field(graph, "nodes")
    assert "comp-a" in nodes
    node = nodes["comp-a"]

    owners = field(node, "owners")
    assert list(owners) == ["team-x"]

    documents = field(node, "documents")
    documents = dict(documents)
    expected_keys = [
        "component.md",
        "interface/library.md",
        "requirements/R-A-001.md",
    ]
    assert sorted(documents.keys()) == expected_keys
    assert set(documents.keys()) == set(expected_keys)

    assert documents["component.md"] == (comp_dir / "component.md").read_text(encoding="utf-8")
    assert documents["interface/library.md"] == (
        comp_dir / "interface" / "library.md"
    ).read_text(encoding="utf-8")
    assert documents["requirements/R-A-001.md"] == (
        comp_dir / "requirements" / "R-A-001.md"
    ).read_text(encoding="utf-8")