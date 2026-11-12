import sys
from pathlib import Path

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
        "Product body.\n",
    )
    _write(
        specs / "architecture" / "a.md",
        "---\n"
        "id: A-ARCH\n"
        "title: Architecture A\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# Architecture A\n"
        "\n"
        "Architecture body.\n",
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
        "Var body.\n",
    )
    _write(
        specs / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Decision one\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "Decision body.\n",
    )

    for sub in ("product", "architecture", "vars", "decisions"):
        _write(specs / sub / "README.md", "# Readme\n\nNot a doc.\n")

    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        'title: "Quoted"\n'
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
        "Foo purpose.\n",
    )
    _write(
        comp / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n\nFoo guarantees something.\n",
    )
    _write(
        comp / "interface" / "cli.md",
        "# CLI\n\n```\nfoo --help\n```\n",
    )

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Intro text.\n"
        "\n"
        "- **Gadget** — a tool\n"
        "  used for tests.\n"
        "- **Widget** — a part.\n",
    )

    # Fake graph-query-engine dependency (flat module shape) so the
    # real views are not required to understand this minimal corpus.
    _write(
        repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py",
        "def load_views(con, repo_root):\n"
        "    return None\n",
    )


def _docs_list(corpus):
    docs = _get(corpus, "docs")
    if docs is None:
        return []
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
    assert corpus is not None

    docs = _docs_list(corpus)
    assert docs, "expected at least one Doc"

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
            f"{rel}: doc_type {_get(doc, 'doc_type')!r} != {dtype!r}"
        )

    # No Doc for any README.md
    for d in docs:
        rp = str(_get(d, "rel_path") or "").replace("\\", "/")
        assert not rp.endswith("README.md"), f"README made a Doc: {rp}"
        p = _get(d, "path")
        if p is not None:
            assert Path(p).name != "README.md", f"README made a Doc: {p}"

    # interface_guarantees keyed by "G-FOO-001"
    components = _get(corpus, "components")
    assert components is not None
    foo = components.get("foo") if isinstance(components, dict) else None
    assert foo is not None, "components has no 'foo' entry"
    guarantees = _get(foo, "interface_guarantees")
    assert guarantees is not None
    assert "G-FOO-001" in guarantees
    assert set(guarantees.keys()) == {"G-FOO-001"}

    # Frontmatter values of component.md
    root_doc = _doc_by_rel(docs, "specs/components/foo/component.md")
    assert root_doc is not None, "no Doc for component.md"
    fm = _get(root_doc, "frontmatter")
    assert fm is not None
    tags = fm.get("tags") if isinstance(fm, dict) else getattr(fm, "tags", None)
    flag = fm.get("flag") if isinstance(fm, dict) else getattr(fm, "flag", None)
    title = fm.get("title") if isinstance(fm, dict) else getattr(fm, "title", None)
    depends_on = (
        fm.get("depends_on") if isinstance(fm, dict) else getattr(fm, "depends_on", None)
    )
    assert tags == [], f"tags: {tags!r}"
    assert flag is False, f"flag: {flag!r}"
    assert title == "Quoted", f"title: {title!r}"
    assert depends_on == ["comp-a", "comp-b"], f"depends_on: {depends_on!r}"

    # id_index holds the four frontmatter ids
    id_index = _get(corpus, "id_index")
    assert id_index is not None
    for doc_id in ("P-X", "A-ARCH", "VAR-V", "D1"):
        assert doc_id in id_index, f"id_index missing {doc_id}"

    # Glossary definitions
    glossary_defs = _get(corpus, "glossary_defs")
    assert glossary_defs is not None
    assert "gadget" in glossary_defs
    assert "widget" in glossary_defs
    gadget = glossary_defs["gadget"]
    assert isinstance(gadget, str)
    assert gadget.startswith("a tool"), f"gadget def: {gadget!r}"
    assert "a tool" in gadget
    assert "used for tests." in gadget
    assert "Widget" not in gadget
    assert "a part." not in gadget