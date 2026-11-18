# hotdocs-criterion: sha256:c7211af3e9d4a45373663fff82ac3b6f26f08ed18a2291d0b5ff5add7c00aeb8
import sys
from pathlib import Path

import pytest

import corpus_loader


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    specs = repo_root / "specs"

    _write(
        specs / "product" / "P-X.md",
        "---\n"
        "id: P-X\n"
        "title: Product X\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# P-X\n"
        "\n"
        "A product capability.\n",
    )
    _write(
        specs / "architecture" / "a.md",
        "---\n"
        "id: ARCH-A\n"
        "title: Architecture A\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# Architecture A\n"
        "\n"
        "Some architecture.\n",
    )
    _write(
        specs / "vars" / "v.md",
        "---\n"
        "id: VAR-V\n"
        "title: Var V\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# VAR-V\n"
        "\n"
        "A var declaration.\n",
    )
    _write(
        specs / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Decision One\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "A decision record.\n",
    )

    for sub in ("product", "architecture", "vars", "decisions"):
        _write(specs / sub / "README.md", "# README\n\nIndex of this directory.\n")

    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: \"Quoted\"\n"
        "status: draft\n"
        "owners: [alice]\n"
        "tags: []\n"
        "flag: false\n"
        "depends_on: [comp-a, comp-b]\n"
        "sealed: true\n"
        "source_path: legacy/foo\n"
        "---\n"
        "\n"
        "# foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A test component.\n",
    )
    _write(
        comp / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n\nFoo always does the thing.\n",
    )
    _write(
        comp / "interface" / "cli.md",
        "# CLI\n\n```\nfoo [--bar]\n```\n",
    )

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary.\n"
        "\n"
        "- **Gadget** \u2014 a tool\n"
        "  used for tests.\n"
        "- **Widget** \u2014 a part.\n",
    )

    # Fake graph-query-engine dependency (flat-module shape), matching the
    # documented load_views(con, repo_root) -> None signature.
    _write(
        repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py",
        "def load_views(con, repo_root):\n"
        "    return None\n",
    )


def _docs_list(corpus):
    docs = _get(corpus, "docs")
    assert docs is not None, "Corpus has no docs"
    if isinstance(docs, dict):
        return list(docs.values())
    return list(docs)


def _doc_by_rel(docs, rel):
    for d in docs:
        rp = _get(d, "rel_path")
        if rp is not None and str(rp).replace("\\", "/") == rel:
            return d
    return None


def test_ac_corpus_003(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    corpus = corpus_loader.load_corpus(repo_root)
    try:
        docs = _docs_list(corpus)

        expected_types = {
            "specs/product/P-X.md": "product",
            "specs/architecture/a.md": "architecture",
            "specs/vars/v.md": "var",
            "specs/decisions/D1.md": "decision",
            "specs/components/foo/interface/guarantees/G-FOO-001.md": "component-interface-guarantee",
            "specs/components/foo/interface/cli.md": "component-interface-cli",
        }
        for rel, dtype in expected_types.items():
            doc = _doc_by_rel(docs, rel)
            assert doc is not None, f"no Doc for {rel}"
            assert _get(doc, "doc_type") == dtype, (
                f"{rel}: expected doc_type {dtype!r}, got {_get(doc, 'doc_type')!r}"
            )

        # No Doc for any README.md
        for d in docs:
            rp = str(_get(d, "rel_path") or "").replace("\\", "/")
            assert not rp.endswith("README.md"), f"README.md became a Doc: {rp}"
            p = _get(d, "path")
            if p is not None:
                assert Path(p).name != "README.md", f"README.md became a Doc: {p}"

        # interface_guarantees keyed by doc_id
        components = _get(corpus, "components")
        assert components is not None
        foo = components.get("foo") if isinstance(components, dict) else None
        assert foo is not None, "components has no 'foo' entry"
        guarantees = _get(foo, "interface_guarantees")
        assert guarantees is not None
        assert "G-FOO-001" in guarantees
        assert list(guarantees.keys()) == ["G-FOO-001"]

        # Frontmatter value parsing on component.md
        root_doc = _doc_by_rel(docs, "specs/components/foo/component.md")
        assert root_doc is not None, "no Doc for component.md"
        fm = _get(root_doc, "frontmatter")
        assert fm is not None

        def fmget(k):
            return fm.get(k) if isinstance(fm, dict) else getattr(fm, k, None)

        assert fmget("tags") == []
        assert fmget("flag") is False
        assert fmget("title") == "Quoted"
        assert fmget("depends_on") == ["comp-a", "comp-b"]

        # id_index holds the four frontmatter ids
        id_index = _get(corpus, "id_index")
        assert id_index is not None
        for doc_id in ("P-X", "ARCH-A", "VAR-V", "D1"):
            assert doc_id in id_index, f"id_index missing {doc_id!r}"

        # Glossary multi-line entry
        gdefs = _get(corpus, "glossary_defs")
        assert gdefs is not None
        assert "gadget" in gdefs, f"glossary_defs keys: {list(gdefs.keys())}"
        gadget = gdefs["gadget"]
        assert isinstance(gadget, str)
        assert "a tool" in gadget
        assert "used for tests." in gadget
        assert not gadget.startswith("\u2014")
        assert not gadget.startswith("-")
        assert gadget == gadget.strip()
        assert "Widget" not in gadget
        assert "widget" in gdefs
        assert "a part." in gdefs["widget"]
    finally:
        graph = _get(corpus, "graph")
        close = getattr(graph, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass