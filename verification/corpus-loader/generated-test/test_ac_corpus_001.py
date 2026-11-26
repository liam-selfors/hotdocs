# hotdocs-criterion: sha256:c43e947dc2c82228902e06cbd77a5d70ea9f8842896e24bff6270e05b6f1e6f9
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
        specs / "glossary.md",
        "# Glossary\n"
        + "\n"
        + "Intro text.\n"
        + "\n"
        + "- **Widget** \u2014 a part.\n",
    )
    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "---\n"
        + "# Foo\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 Foo MUST do a thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        + "```gherkin\nGiven x\nWhen y\nThen z\n```\n",
    )
    _write(comp / "interface" / "library.md", "# Library\n\n```\nfoo() -> None\n```\n")
    _write(comp / "interface" / "data" / "Thing.md", "# `Thing`\n\nA thing.\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(comp / "README.md", "# Foo readme\n")
    _write(
        specs / "decisions" / "D200.md",
        "---\n"
        + "id: D200\n"
        + "title: A decision\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "---\n"
        + "# D200\n\nDecided.\n",
    )


def _docs_list(docs):
    if isinstance(docs, dict):
        return list(docs.values())
    return list(docs)


def test_ac_corpus_001(tmp_path):
    repo_root = tmp_path.resolve()
    _build_fixture(repo_root)

    corpus = corpus_loader.load_corpus(repo_root)
    try:
        components = field(corpus, "components")
        assert "foo" in components
        foo = components["foo"]

        root = field(foo, "root")
        assert root is not None
        assert field(root, "frontmatter") == {
            "id": "comp-foo",
            "title": "Foo",
            "status": "draft",
            "owners": ["team-a"],
            "sealed": True,
            "source_path": "legacy/foo/",
        }
        text = (repo_root / "specs/components/foo/component.md").read_text(encoding="utf-8")
        lines = text.splitlines()
        closing = [i for i, line in enumerate(lines) if line == "---"][1]
        expected_body = "\n".join(lines[closing + 1:])
        assert expected_body == "# Foo"
        assert field(root, "body") == expected_body
        assert not field(root, "body").endswith("\n")
        assert field(root, "doc_type") == "component-root"
        assert field(root, "doc_id") == "comp-foo"

        requirements = field(foo, "requirements")
        assert list(requirements.keys()) == ["R-FOO-001"]
        assert field(requirements["R-FOO-001"], "doc_type") == "component-requirement"
        assert field(requirements["R-FOO-001"], "doc_id") == "R-FOO-001"

        acceptance = field(foo, "acceptance")
        assert list(acceptance.keys()) == ["AC-FOO-001"]
        assert field(acceptance["AC-FOO-001"], "doc_type") == "component-acceptance"
        assert field(acceptance["AC-FOO-001"], "doc_id") == "AC-FOO-001"

        interface_data = field(foo, "interface_data")
        assert list(interface_data.keys()) == ["Thing"]
        assert field(interface_data["Thing"], "doc_type") == "component-interface-data"

        lib = field(foo, "interface_library")
        assert lib is not None
        assert field(lib, "doc_type") == "component-interface-library"
        assert field(foo, "interface_cli") is None

        constraints = field(foo, "constraints")
        assert constraints is not None
        assert field(constraints, "doc_type") == "component-constraints"

        docs = _docs_list(field(corpus, "docs"))
        expected_types = {
            "specs/components/foo/component.md": "component-root",
            "specs/components/foo/requirements/R-FOO-001.md": "component-requirement",
            "specs/components/foo/acceptance/AC-FOO-001.md": "component-acceptance",
            "specs/components/foo/interface/library.md": "component-interface-library",
            "specs/components/foo/interface/data/Thing.md": "component-interface-data",
            "specs/components/foo/constraints.md": "component-constraints",
            "specs/decisions/D200.md": "decision",
        }
        by_rel = {}
        for doc in docs:
            rel = field(doc, "rel_path")
            path = field(doc, "path")
            assert isinstance(rel, str)
            assert not Path(rel).is_absolute()
            assert "\\" not in rel
            assert Path(path).is_absolute()
            assert Path(path) == repo_root / rel
            by_rel[rel] = doc
        assert set(by_rel.keys()) == set(expected_types.keys())
        for rel, doc_type in expected_types.items():
            assert field(by_rel[rel], "doc_type") == doc_type
        for rel in by_rel:
            assert not rel.endswith("README.md")
            assert rel != "specs/glossary.md"

        id_index = field(corpus, "id_index")
        assert "comp-foo" in id_index
        assert "D200" in id_index
        assert field(id_index["D200"], "doc_type") == "decision"
        assert field(id_index["comp-foo"], "doc_type") == "component-root"

        glossary_defs = field(corpus, "glossary_defs")
        assert glossary_defs["widget"] == "a part."

        glossary_files = [Path(p) for p in field(corpus, "glossary_files")]
        glossary_path = repo_root / "specs" / "glossary.md"
        assert glossary_path in glossary_files
        for p in glossary_files:
            assert p.is_absolute()
    finally:
        try:
            graph = field(corpus, "graph")
            if graph is not None:
                graph.close()
        except Exception:
            pass