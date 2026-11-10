import tempfile
from pathlib import Path

import corpus_loader


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _setup_repo(repo_root: Path) -> None:
    # Fake dependency: comp-graph-query-engine, flat module shape.
    _write(
        repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py",
        "def load_views(con, repo_root):\n"
        "    return None\n",
    )

    _write(
        repo_root / "specs" / "product" / "P-X.md",
        "---\n"
        "id: P-X\n"
        "title: Product X\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "Product body text.\n",
    )

    _write(
        repo_root / "specs" / "architecture" / "a.md",
        "---\n"
        "id: A-ONE\n"
        "title: Architecture One\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "Architecture body text.\n",
    )

    _write(
        repo_root / "specs" / "vars" / "v.md",
        "---\n"
        "id: VAR-V\n"
        "title: Var V\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "Var body text.\n",
    )

    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Decision One\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "Decision body text.\n",
    )

    _write(
        repo_root
        / "specs"
        / "components"
        / "foo"
        / "interface"
        / "guarantees"
        / "G-FOO-001.md",
        "Guarantee text for G-FOO-001.\n",
    )

    _write(
        repo_root / "specs" / "components" / "foo" / "interface" / "cli.md",
        "CLI interface text.\n",
    )

    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "tags: []\n"
        "flag: false\n"
        'title: "Quoted"\n'
        "depends_on: [comp-a, comp-b]\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: fake/foo-source\n"
        "---\n"
        "Foo component body.\n",
    )

    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Gadget** — a tool\n"
        "used for tests.\n"
        "- **Widget** — a part.\n",
    )


def test_ac_corpus_003():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _setup_repo(repo_root)

        corpus = corpus_loader.load_corpus(repo_root)

        docs = _field(corpus, "docs")
        docs_by_rel = {}
        for d in docs:
            rel = _field(d, "rel_path")
            docs_by_rel[rel] = d

        product_doc = docs_by_rel["specs/product/P-X.md"]
        architecture_doc = docs_by_rel["specs/architecture/a.md"]
        var_doc = docs_by_rel["specs/vars/v.md"]
        decision_doc = docs_by_rel["specs/decisions/D1.md"]
        guarantee_doc = docs_by_rel[
            "specs/components/foo/interface/guarantees/G-FOO-001.md"
        ]
        cli_doc = docs_by_rel["specs/components/foo/interface/cli.md"]

        assert _field(product_doc, "doc_type") == "product"
        assert _field(architecture_doc, "doc_type") == "architecture"
        assert _field(var_doc, "doc_type") == "var"
        assert _field(decision_doc, "doc_type") == "decision"
        assert (
            _field(guarantee_doc, "doc_type")
            == "component-interface-guarantee"
        )
        assert _field(cli_doc, "doc_type") == "component-interface-cli"

        components = _field(corpus, "components")
        foo_component = _field(components, "foo")
        assert foo_component is not None

        interface_guarantees = _field(foo_component, "interface_guarantees")
        assert _field(interface_guarantees, "G-FOO-001") is not None

        foo_root_doc = _field(foo_component, "root")
        frontmatter = _field(foo_root_doc, "frontmatter")

        assert _field(frontmatter, "tags") == []
        assert _field(frontmatter, "flag") is False
        assert _field(frontmatter, "title") == "Quoted"
        assert _field(frontmatter, "depends_on") == ["comp-a", "comp-b"]

        id_index = _field(corpus, "id_index")
        for expected_id in ("P-X", "A-ONE", "VAR-V", "D1"):
            assert expected_id in id_index

        glossary_defs = _field(corpus, "glossary_defs")
        assert "gadget" in glossary_defs
        gadget_text = _field(glossary_defs, "gadget")
        assert "a tool" in gadget_text
        assert "used for tests." in gadget_text
        assert "widget" in glossary_defs