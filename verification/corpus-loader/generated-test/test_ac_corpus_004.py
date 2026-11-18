# hotdocs-criterion: sha256:86e2b8a38332a541223b65b64e2e521f3048f1df9945e786ad7bd4b6efba1ed7
import os
from pathlib import Path

import corpus_loader


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _tool_root() -> Path:
    here = Path(corpus_loader.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    raise AssertionError("no gen directory above corpus_loader module")


REQ_TEXT = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 The foo component MUST do the foo thing.\n"
)

AC_TEXT = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given a foo\n"
    "When it runs\n"
    "Then it does the foo thing\n"
    "```\n"
)

COMPONENT_TEXT = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [alice]\n"
    "depends_on: []\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Does the foo thing.\n"
)

GLOSSARY_TEXT = (
    "# Glossary\n"
    "\n"
    "- **Foo** \u2014 a thing that does foo.\n"
)

DECISION_TEXT = (
    "---\n"
    "id: D1\n"
    "title: First decision\n"
    "status: draft\n"
    "owners: [alice]\n"
    "---\n"
    "\n"
    "# D1\n"
    "\n"
    "A decision.\n"
)

VAR_TEXT = (
    "---\n"
    "id: VAR-FOO\n"
    "title: Foo var\n"
    "status: draft\n"
    "owners: [alice]\n"
    "---\n"
    "\n"
    "# VAR-FOO\n"
    "\n"
    "A variable.\n"
)


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    _write(comp / "component.md", COMPONENT_TEXT)
    _write(comp / "requirements" / "R-FOO-001.md", REQ_TEXT)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_TEXT)
    _write(specs / "glossary.md", GLOSSARY_TEXT)
    _write(specs / "decisions" / "D1.md", DECISION_TEXT)
    _write(specs / "vars" / "VAR-FOO.md", VAR_TEXT)


def _docs_list(corpus):
    docs = field(corpus, "docs")
    if isinstance(docs, dict):
        return list(docs.values())
    return list(docs)


def _find_doc(corpus, rel_path):
    for d in _docs_list(corpus):
        if str(field(d, "rel_path")).replace(os.sep, "/") == rel_path:
            return d
    raise AssertionError(
        f"no Doc with rel_path {rel_path!r}; have "
        f"{[field(d, 'rel_path') for d in _docs_list(corpus)]!r}"
    )


def test_ac_corpus_004(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    assert not (repo_root / "gen").exists()

    tool_root = _tool_root()
    assert (tool_root / "gen" / "graph-query-engine").is_dir()

    corpus = corpus_loader.load_corpus(repo_root)

    # Requirement doc: no frontmatter.
    req_rel = "specs/components/foo/requirements/R-FOO-001.md"
    req_doc = _find_doc(corpus, req_rel)
    assert field(req_doc, "has_frontmatter") is False
    assert dict(field(req_doc, "frontmatter")) == {}
    req_file_text = (repo_root / req_rel).read_bytes().decode("utf-8")
    assert req_file_text == REQ_TEXT
    assert field(req_doc, "body") == req_file_text

    # component.md doc: has frontmatter.
    comp_doc = _find_doc(corpus, "specs/components/foo/component.md")
    assert field(comp_doc, "has_frontmatter") is True

    # graph answers the nodes query, graph-query-engine loaded from the tool root.
    graph = field(corpus, "graph")
    row = graph.execute("SELECT count(*) FROM nodes").fetchone()
    assert row is not None
    count = row[0]
    assert isinstance(count, int)
    assert count >= 1

    # No gen/ directory was created under repo_root; the engine came from the tool root.
    assert not (repo_root / "gen").exists()