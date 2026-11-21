# hotdocs-criterion: sha256:9fdc66a35da43f6f1401afd55d01fecd0412f39e5e9604bf8c3d1f8c5b7e8f03
import sys
from pathlib import Path

import corpus_loader


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fm(lines):
    return "---\n" + "\n".join(lines) + "\n---\n"


def _build_fixture(repo_root, log_path):
    specs = repo_root / "specs"

    _write(
        specs / "product" / "P-X.md",
        _fm(["id: P-X", "title: Product X", "status: draft", "owners: [alice]"])
        + "\n# P-X\n\nA product.\n",
    )
    _write(
        specs / "architecture" / "a.md",
        _fm(["id: ARCH-A", "title: Arch A", "status: draft", "owners: [alice]"])
        + "\n# Arch A\n\nAn architecture doc.\n",
    )
    _write(
        specs / "vars" / "v.md",
        _fm(["id: VAR-V", "title: Var V", "status: draft", "owners: [alice]"])
        + "\n# VAR-V\n\nA var.\n",
    )
    _write(
        specs / "decisions" / "D1.md",
        _fm(["id: D1", "title: Decision One", "status: draft", "owners: [alice]"])
        + "\n# D1\n\nA decision.\n",
    )

    for sub in ("product", "architecture", "vars", "decisions"):
        _write(specs / sub / "README.md", "# README\n\nIndex of " + sub + ".\n")

    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        _fm(
            [
                "id: comp-foo",
                'title: "Quoted"',
                "status: draft",
                "owners: [alice]",
                "tags: []",
                "flag: false",
                "depends_on: [comp-a, comp-b]",
                "sealed: true",
                "source_path: legacy/foo/",
            ]
        )
        + "\n# Foo\n\n## Purpose\n\nDoes foo things.\n",
    )
    _write(
        comp / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n\nFoo always holds.\n",
    )
    _write(comp / "interface" / "cli.md", "# CLI\n\n```\nfoo run\n```\n")

    _write(
        specs / "glossary.md",
        "# Glossary\n\n"
        "- **Gadget** \u2014 a tool\n"
        "  used for tests.\n"
        "- **Widget** \u2014 a part.\n",
    )

    # Fake graph-query-engine dependency (flat module shape).
    fake_src = (
        "def load_views(con, repo_root):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('load_views\\n')\n"
        "    return None\n"
    )
    _write(repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py", fake_src)


def _docs_list(corpus):
    docs = field(corpus, "docs")
    if isinstance(docs, dict):
        return list(docs.values())
    return list(docs)


def test_ac_corpus_003(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "gqe_calls.log"
    _build_fixture(repo_root, log_path)

    corpus = corpus_loader.load_corpus(repo_root)

    docs = _docs_list(corpus)
    by_rel = {}
    for d in docs:
        by_rel[str(field(d, "rel_path")).replace("\\", "/")] = d

    expected_types = {
        "specs/product/P-X.md": "product",
        "specs/architecture/a.md": "architecture",
        "specs/vars/v.md": "var",
        "specs/decisions/D1.md": "decision",
        "specs/components/foo/interface/guarantees/G-FOO-001.md": "component-interface-guarantee",
        "specs/components/foo/interface/cli.md": "component-interface-cli",
    }
    for rel, dtype in expected_types.items():
        assert rel in by_rel, "missing Doc for " + rel + "; have " + repr(sorted(by_rel))
        assert field(by_rel[rel], "doc_type") == dtype, (
            rel + " doc_type " + repr(field(by_rel[rel], "doc_type"))
        )

    # interface_guarantees keyed by doc_id
    components = field(corpus, "components")
    foo = components["foo"]
    guarantees = field(foo, "interface_guarantees")
    assert list(guarantees.keys()) == ["G-FOO-001"]

    # frontmatter value parsing on component.md
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
        assert doc_id in id_index, doc_id + " not in id_index " + repr(list(id_index))

    # glossary
    gdefs = field(corpus, "glossary_defs")
    assert "gadget" in gdefs
    assert "a tool" in gdefs["gadget"]
    assert "used for tests." in gdefs["gadget"]
    assert "widget" in gdefs

    # no Doc for any README.md
    for rel in by_rel:
        assert Path(rel).name != "README.md", "README made into Doc: " + rel