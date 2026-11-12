import os
from pathlib import Path

import corpus_loader


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


REQ_TEXT = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `foo()` MUST return the configured value.\n"
)

COMPONENT_TEXT = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [alice]\n"
    "sealed: true\n"
    "source_path: legacy/foo\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Returns a configured value.\n"
)

ACCEPTANCE_TEXT = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given a configured value\n"
    "When foo() runs\n"
    "Then it returns that value\n"
    "```\n"
)

GLOSSARY_TEXT = (
    "# Glossary\n"
    "\n"
    "- **Widget** \u2014 a small thing.\n"
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
    "id: VAR-FOO-PATH\n"
    "title: Foo path\n"
    "status: draft\n"
    "owners: [alice]\n"
    "---\n"
    "\n"
    "# VAR-FOO-PATH\n"
    "\n"
    "A path.\n"
)

ARCH_TEXT = (
    "---\n"
    "id: arch-overview\n"
    "title: Overview\n"
    "status: draft\n"
    "owners: [alice]\n"
    "---\n"
    "\n"
    "# Overview\n"
)


def _build_repo(root: Path) -> Path:
    specs = root / "specs"
    comp = specs / "components" / "foo"
    _write(comp / "component.md", COMPONENT_TEXT)
    _write(comp / "requirements" / "R-FOO-001.md", REQ_TEXT)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_TEXT)
    _write(specs / "glossary.md", GLOSSARY_TEXT)
    _write(specs / "decisions" / "D1.md", DECISION_TEXT)
    _write(specs / "vars" / "VAR-FOO-PATH.md", VAR_TEXT)
    _write(specs / "architecture" / "overview.md", ARCH_TEXT)
    return root


def _docs_list(corpus):
    docs = _get(corpus, "docs")
    if isinstance(docs, dict):
        return list(docs.values())
    return list(docs or [])


def _find_doc(corpus, rel_path):
    for d in _docs_list(corpus):
        if _get(d, "rel_path") == rel_path:
            return d
    return None


def test_ac_corpus_004_no_frontmatter_requirement_and_graph_from_tool_root(tmp_path):
    repo_root = _build_repo(tmp_path / "repo")
    assert not (repo_root / "gen").exists()

    corpus = corpus_loader.load_corpus(repo_root)

    req_rel = "specs/components/foo/requirements/R-FOO-001.md"
    comp_rel = "specs/components/foo/component.md"

    req_doc = _find_doc(corpus, req_rel)
    if req_doc is None:
        components = _get(corpus, "components") or {}
        foo = components.get("foo") if isinstance(components, dict) else None
        if foo is not None:
            reqs = _get(foo, "requirements") or {}
            req_doc = reqs.get("R-FOO-001")
    assert req_doc is not None, "requirement Doc not found in corpus"

    req_file_text = (repo_root / req_rel).read_text(encoding="utf-8")
    assert _get(req_doc, "has_frontmatter") is False
    assert _get(req_doc, "frontmatter") == {}
    assert _get(req_doc, "body") == req_file_text
    assert _get(req_doc, "doc_id") == "R-FOO-001"
    assert _get(req_doc, "doc_type") == "component-requirement"

    comp_doc = _find_doc(corpus, comp_rel)
    if comp_doc is None:
        components = _get(corpus, "components") or {}
        foo = components.get("foo") if isinstance(components, dict) else None
        if foo is not None:
            comp_doc = _get(foo, "root")
    assert comp_doc is not None, "component.md Doc not found in corpus"
    assert _get(comp_doc, "has_frontmatter") is True

    graph = _get(corpus, "graph")
    assert graph is not None
    row = graph.execute("SELECT count(*) FROM nodes").fetchone()
    assert row is not None
    count = row[0]
    assert isinstance(count, int)
    assert count >= 0

    # The fake repo_root must still have no gen/ directory: the
    # graph-query-engine was resolved from the tool root instead.
    assert not (repo_root / "gen").exists()