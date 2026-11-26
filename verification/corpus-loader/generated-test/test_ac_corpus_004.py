# hotdocs-criterion: sha256:9950274835c9201959a596fe07110e58548dacf8ad1425e723e613201dd96581
from pathlib import Path

import corpus_loader


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component for the corpus loader.\n"
    )
    _write(comp_dir / "component.md", component_md)

    requirement_text = (
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 Foo MUST do the foo thing.\n"
    )
    _write(comp_dir / "requirements" / "R-FOO-001.md", requirement_text)

    acceptance_text = (
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "Given foo\n"
        "When foo runs\n"
        "Then foo happens\n"
    )
    _write(comp_dir / "acceptance" / "AC-FOO-001.md", acceptance_text)

    glossary_text = (
        "# Glossary\n"
        "\n"
        "- **Foo** \u2014 a fixture term.\n"
    )
    _write(repo_root / "specs" / "glossary.md", glossary_text)

    return comp_dir


def _iter_docs(corpus):
    docs = field(corpus, "docs")
    if isinstance(docs, dict):
        return list(docs.values())
    return list(docs)


def _find_doc(corpus, rel_path):
    for doc in _iter_docs(corpus):
        if str(field(doc, "rel_path")) == rel_path:
            return doc
    raise AssertionError("no Doc with rel_path " + repr(rel_path))


def test_ac_corpus_004(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp_dir = _build_fixture(repo_root)

    assert not (repo_root / "gen").exists()

    corpus = corpus_loader.load_corpus(repo_root)

    req_rel = "specs/components/foo/requirements/R-FOO-001.md"
    req_doc = _find_doc(corpus, req_rel)
    req_text = (comp_dir / "requirements" / "R-FOO-001.md").read_text(encoding="utf-8")

    assert field(req_doc, "has_frontmatter") is False
    assert field(req_doc, "frontmatter") == {}
    assert field(req_doc, "body") == req_text

    comp_doc = _find_doc(corpus, "specs/components/foo/component.md")
    assert field(comp_doc, "has_frontmatter") is True

    graph = field(corpus, "graph")
    row = graph.execute("SELECT count(*) FROM nodes").fetchone()
    assert row is not None
    count = row[0]
    assert isinstance(count, int)
    assert count >= 1

    # Still no gen/ under repo_root: the views came from the tool root.
    assert not (repo_root / "gen").exists()