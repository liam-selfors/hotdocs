# hotdocs-criterion: sha256:6d076313320e6b12711adeb060225a2c6674fa46ac03ca707dae7862e99d9046
# AC-GRAPH-011 (Covers: R-GRAPH-003)
#
# Given comp-a whose component.md has the frontmatter owners: [team-x]
#   and whose directory also holds requirements/R-A-001.md and
#   interface/library.md
# When build_corpus_graph runs
# Then comp-a's node has owners ["team-x"], and documents whose keys are
#   exactly "component.md", "interface/library.md" and
#   "requirements/R-A-001.md", each mapped to that file's whole text
#
# Note: the criterion requires the documents keys to be exactly these
# three files, so the fixture deliberately holds no acceptance/ file
# (any acceptance/*.md would itself be a document under the directory).
# No spec-linter precondition is involved in this criterion.

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
    "A small fixture component used to check owners and documents.\n"
)

REQUIREMENT_MD = (
    "# R-A-001\n"
    "\n"
    "**R-A-001** — Component A MUST do one small thing.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "do_thing() -> None\n"
    "```\n"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _build_fixture(repo_root: Path) -> Path:
    comp_dir = repo_root / "specs" / "components" / "a"
    _write(comp_dir / "component.md", COMPONENT_MD)
    _write(comp_dir / "requirements" / "R-A-001.md", REQUIREMENT_MD)
    _write(comp_dir / "interface" / "library.md", LIBRARY_MD)
    return comp_dir


def test_ac_graph_011_owners_and_documents(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp_dir = _build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    assert "comp-a" in nodes, "comp-a missing from nodes: " + repr(list(nodes))
    node = nodes["comp-a"]

    owners = field(node, "owners")
    assert list(owners) == ["team-x"]

    documents = field(node, "documents")
    expected_keys = ["component.md", "interface/library.md", "requirements/R-A-001.md"]
    assert sorted(documents.keys()) == expected_keys

    expected_texts = {
        "component.md": (comp_dir / "component.md").read_bytes().decode("utf-8"),
        "interface/library.md": (comp_dir / "interface" / "library.md").read_bytes().decode("utf-8"),
        "requirements/R-A-001.md": (comp_dir / "requirements" / "R-A-001.md").read_bytes().decode("utf-8"),
    }
    assert expected_texts["component.md"] == COMPONENT_MD
    assert expected_texts["interface/library.md"] == LIBRARY_MD
    assert expected_texts["requirements/R-A-001.md"] == REQUIREMENT_MD

    for key in expected_keys:
        assert documents[key] == expected_texts[key], "document text mismatch for " + repr(key)

    # build_corpus_graph writes nothing
    assert not (repo_root / "verification" / "corpus-graph.json").exists()