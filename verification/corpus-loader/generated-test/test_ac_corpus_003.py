# hotdocs-criterion: sha256:f5637bc08bdec4fcadae30f51a9d224bdb928f5e49104b2c1eebdc5c617d7c21
from pathlib import Path

import corpus_loader


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    specs = repo_root / "specs"

    _write(
        specs / "product" / "P-X.md",
        "---\n"
        "id: P-X\n"
        "title: Product X\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "# P-X\n"
        "\n"
        "A product capability.\n",
    )
    _write(
        specs / "architecture" / "a.md",
        "---\n"
        "id: arch-a\n"
        "title: Architecture A\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "# Architecture A\n",
    )
    _write(
        specs / "vars" / "v.md",
        "---\n"
        "id: VAR-V\n"
        "title: Var V\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "# VAR-V\n",
    )
    _write(
        specs / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Decision one\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "# D1\n",
    )

    for d in ("product", "architecture", "vars", "decisions"):
        _write(specs / d / "README.md", "# README for " + d + "\n")

    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        'title: "Quoted"\n'
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "tags: []\n"
        "flag: false\n"
        "depends_on: [comp-a, comp-b]\n"
        "---\n"
        "# comp-foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Testing fixture.\n",
    )
    _write(
        comp / "interface" / "guarantees" / "G-FOO-001.md",
        "**G-FOO-001** — foo always works.\n",
    )
    _write(
        comp / "interface" / "cli.md",
        "# CLI\n\n```\nfoo run\n```\n",
    )

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Gadget** — a tool\n"
        "  used for tests.\n"
        "- **Widget** — a part.\n",
    )

    # Fake graph-query-engine, flat-module shape, matching load_views's signature.
    fake_dir = repo_root / "gen" / "graph-query-engine"
    fake_dir.mkdir(parents=True, exist_ok=True)
    log_path = repo_root / "gqe_calls.log"
    src = (
        "from pathlib import Path\n"
        "\n"
        "def load_views(con, repo_root):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "        fh.write('load_views\\n')\n"
        "    return None\n"
    )
    (fake_dir / "graph_query_engine.py").write_text(src, encoding="utf-8")


def _docs_list(corpus):
    docs = field(corpus, "docs")
    if isinstance(docs, dict):
        return list(docs.values())
    return list(docs)


def test_ac_corpus_003(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    corpus = corpus_loader.load_corpus(repo_root)

    docs = _docs_list(corpus)
    by_rel = {field(d, "rel_path"): d for d in docs}

    expected_types = {
        "specs/product/P-X.md": "product",
        "specs/architecture/a.md": "architecture",
        "specs/vars/v.md": "var",
        "specs/decisions/D1.md": "decision",
        "specs/components/foo/interface/guarantees/G-FOO-001.md": "component-interface-guarantee",
        "specs/components/foo/interface/cli.md": "component-interface-cli",
    }
    for rel, dtype in expected_types.items():
        assert rel in by_rel, "missing Doc for " + rel
        assert field(by_rel[rel], "doc_type") == dtype, rel

    # No Doc for any README.md
    for d in docs:
        rel = field(d, "rel_path")
        assert Path(rel).name != "README.md", rel

    components = field(corpus, "components")
    assert "foo" in components
    foo = components["foo"]
    guarantees = field(foo, "interface_guarantees")
    assert list(guarantees.keys()) == ["G-FOO-001"]

    root = field(foo, "root")
    assert root is not None
    fm = field(root, "frontmatter")
    assert fm["tags"] == []
    assert fm["flag"] is False
    assert fm["title"] == "Quoted"
    assert fm["depends_on"] == ["comp-a", "comp-b"]

    id_index = field(corpus, "id_index")
    for doc_id in ("P-X", "arch-a", "VAR-V", "D1"):
        assert doc_id in id_index, doc_id

    glossary_defs = field(corpus, "glossary_defs")
    assert "gadget" in glossary_defs
    gadget = glossary_defs["gadget"]
    assert "a tool" in gadget
    assert "used for tests." in gadget
    assert "Widget" not in gadget
    assert "widget" in glossary_defs