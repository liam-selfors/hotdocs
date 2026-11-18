# hotdocs-criterion: sha256:86e2b8a38332a541223b65b64e2e521f3048f1df9945e786ad7bd4b6efba1ed7
from pathlib import Path

import corpus_loader


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does a thing.\n",
    )
    req_text = (
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 Foo MUST do the thing.\n"
    )
    _write(comp_dir / "requirements" / "R-FOO-001.md", req_text)
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "Foo does the thing.\n",
    )
    return comp_dir


def _iter_docs(corpus):
    docs = field(corpus, "docs")
    if isinstance(docs, dict):
        return list(docs.values())
    return list(docs)


def _find_doc(corpus, rel_path):
    for doc in _iter_docs(corpus):
        if field(doc, "rel_path") == rel_path:
            return doc
    raise AssertionError("no Doc with rel_path " + repr(rel_path))


def test_ac_corpus_004_frontmatterless_requirement_and_graph(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp_dir = _build_fixture(repo_root)
    assert not (repo_root / "gen").exists()

    corpus = corpus_loader.load_corpus(repo_root)

    req_path = comp_dir / "requirements" / "R-FOO-001.md"
    req_doc = _find_doc(corpus, "specs/components/foo/requirements/R-FOO-001.md")
    assert field(req_doc, "has_frontmatter") is False
    assert field(req_doc, "frontmatter") == {}
    assert field(req_doc, "body") == req_path.read_text(encoding="utf-8")
    assert field(req_doc, "doc_type") == "component-requirement"
    assert field(req_doc, "doc_id") == "R-FOO-001"

    comp_doc = _find_doc(corpus, "specs/components/foo/component.md")
    assert field(comp_doc, "has_frontmatter") is True
    assert field(comp_doc, "doc_type") == "component-root"
    assert field(field(comp_doc, "frontmatter"), "id") == "comp-foo"

    # graph-query-engine must have been loaded from the tool root, since
    # repo_root has no gen/ directory.
    assert not (repo_root / "gen").exists()
    graph = field(corpus, "graph")
    row = graph.execute("SELECT count(*) FROM nodes").fetchone()
    assert row is not None
    assert isinstance(row[0], int)
    assert row[0] >= 0