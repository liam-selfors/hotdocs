"""AC-CORPUS-003: load_corpus classifies docs, parses frontmatter scalars and
lists, indexes ids, reads multi-line glossary entries, and skips README.md."""

from pathlib import Path

import corpus_loader


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _frontmatter_doc(doc_id: str, title: str, extra: str = "", body: str = "Body text.\n") -> str:
    return (
        "---\n"
        f"id: {doc_id}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [tester]\n"
        f"{extra}"
        "---\n"
        "\n"
        f"{body}"
    )


def _build_fixture(repo_root: Path) -> None:
    specs = repo_root / "specs"

    _write(specs / "product" / "P-X.md", _frontmatter_doc("P-X", "Product X"))
    _write(specs / "architecture" / "a.md", _frontmatter_doc("ARCH-A", "Architecture A"))
    _write(specs / "vars" / "v.md", _frontmatter_doc("VAR-V", "Var V"))
    _write(specs / "decisions" / "D1.md", _frontmatter_doc("D1", "Decision One"))

    for sub in ("product", "architecture", "vars", "decisions"):
        _write(specs / sub / "README.md", f"# {sub}\n\nIndex of {sub}.\n")

    comp_dir = specs / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        'title: "Quoted"\n'
        "status: draft\n"
        "owners: [tester]\n"
        "tags: []\n"
        "flag: false\n"
        "depends_on: [comp-a, comp-b]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n\n## Purpose\n\nA test component.\n",
    )
    _write(
        comp_dir / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n\nFoo always does the thing.\n",
    )
    _write(
        comp_dir / "interface" / "cli.md",
        "# CLI\n\n```\nfoo run\n```\n",
    )

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary.\n"
        "\n"
        "- **Gadget** — a tool\n"
        "  used for tests.\n"
        "- **Widget** — a part.\n",
    )

    # Fake graph-query-engine: matches documented load_views(con, repo_root) -> None.
    _write(
        repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py",
        "def load_views(con, repo_root):\n"
        "    return None\n",
    )


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
    try:
        docs = _docs_list(corpus)
        by_rel = {}
        for d in docs:
            rel = str(field(d, "rel_path")).replace("\\", "/")
            by_rel[rel] = d

        expected_types = {
            "specs/product/P-X.md": "product",
            "specs/architecture/a.md": "architecture",
            "specs/vars/v.md": "var",
            "specs/decisions/D1.md": "decision",
            "specs/components/foo/interface/guarantees/G-FOO-001.md": "component-interface-guarantee",
            "specs/components/foo/interface/cli.md": "component-interface-cli",
        }
        for rel, dtype in expected_types.items():
            assert rel in by_rel, f"missing Doc for {rel}; have {sorted(by_rel)}"
            assert field(by_rel[rel], "doc_type") == dtype, (
                f"{rel}: expected doc_type {dtype!r}, got {field(by_rel[rel], 'doc_type')!r}"
            )

        # No Doc for any README.md
        readme_docs = [r for r in by_rel if r.split("/")[-1] == "README.md"]
        assert readme_docs == [], f"README.md files became Docs: {readme_docs}"

        # interface_guarantees keyed by doc_id
        components = field(corpus, "components")
        assert "foo" in components
        foo = components["foo"]
        guarantees = field(foo, "interface_guarantees")
        assert list(guarantees.keys()) == ["G-FOO-001"]
        assert field(guarantees["G-FOO-001"], "doc_id") == "G-FOO-001"

        # Frontmatter value parsing on component.md
        root_rel = "specs/components/foo/component.md"
        assert root_rel in by_rel
        fm = field(by_rel[root_rel], "frontmatter")
        assert fm["tags"] == []
        assert fm["flag"] is False
        assert fm["title"] == "Quoted"
        assert fm["depends_on"] == ["comp-a", "comp-b"]

        # id_index holds the four frontmatter ids
        id_index = field(corpus, "id_index")
        for doc_id in ("P-X", "ARCH-A", "VAR-V", "D1"):
            assert doc_id in id_index, f"{doc_id} missing from id_index: {sorted(id_index)}"

        # Glossary multi-line entry
        glossary_defs = field(corpus, "glossary_defs")
        assert "gadget" in glossary_defs
        gadget = glossary_defs["gadget"]
        assert "a tool" in gadget
        assert "used for tests." in gadget
        assert "a part" not in gadget
        assert "Widget" not in gadget
        assert "widget" in glossary_defs
    finally:
        try:
            graph = field(corpus, "graph")
            if graph is not None and hasattr(graph, "close"):
                graph.close()
        except Exception:
            pass