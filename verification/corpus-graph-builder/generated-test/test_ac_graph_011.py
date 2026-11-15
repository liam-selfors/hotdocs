"""AC-GRAPH-011 (Covers: R-GRAPH-003).

Given comp-a whose component.md has the frontmatter owners: [team-x]
  and whose directory also holds requirements/R-A-001.md and
  interface/library.md
When build_corpus_graph runs
Then comp-a's node has owners ["team-x"], and documents whose keys are
  exactly "component.md", "interface/library.md" and
  "requirements/R-A-001.md", each mapped to that file's whole text
"""

from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def lookup(container, key):
    if isinstance(container, dict):
        return container[key]
    return getattr(container, key)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write raw bytes so the on-disk text is exactly `text`, with no
    # newline translation.
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
    "A small fixture component used to check graph documents.\n"
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
    "do_thing(x: int) -> int\n"
    "```\n"
    "\n"
    "Returns its argument unchanged.\n"
)


def test_ac_graph_011_owners_and_documents(tmp_path):
    repo_root = tmp_path / "repo"
    comp_dir = repo_root / "specs" / "components" / "a"

    _write(comp_dir / "component.md", COMPONENT_MD)
    _write(comp_dir / "requirements" / "R-A-001.md", REQUIREMENT_MD)
    _write(comp_dir / "interface" / "library.md", LIBRARY_MD)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    node = lookup(nodes, "comp-a")

    owners = field(node, "owners")
    assert list(owners) == ["team-x"]

    documents = field(node, "documents")
    documents = dict(documents)

    expected = {
        "component.md": COMPONENT_MD,
        "interface/library.md": LIBRARY_MD,
        "requirements/R-A-001.md": REQUIREMENT_MD,
    }

    assert set(documents.keys()) == set(expected.keys())
    for key, text in expected.items():
        assert documents[key] == text, f"documents[{key!r}] is not the file's whole text"