# hotdocs-criterion: sha256:09fbb7199e6bbb7e756146cd7327dab9ed8791eea7774f53e30ea8ad203456b3
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
        "# Glossary\n\nCanonical vocabulary.\n\n- **Widget** — a part.\n",
    )

    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "# Foo\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — foo MUST do a thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\n\nThe thing is done.\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo() -> None\n```\n",
    )
    _write(
        comp / "interface" / "data" / "Thing.md",
        "# `Thing`\n\nA thing.\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(comp / "README.md", "# Readme\n\nNot a spec doc.\n")

    _write(
        specs / "decisions" / "D200.md",
        "---\n"
        "id: D200\n"
        "title: A decision\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "# D200\n\nDecided.\n",
    )

    # Fake graph-query-engine dependency, flat-module shape.
    log_path = repo_root / "gqe_calls.log"
    fake_src = (
        "def load_views(con, repo_root):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "        fh.write('load_views\\n')\n"
        "    return None\n"
    )
    _write(repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py", fake_src)
    return log_path


def _docs_list(corpus):
    docs = field(corpus, "docs")
    if isinstance(docs, dict):
        return list(docs.values())
    return list(docs)


def test_ac_corpus_001_load_corpus_builds_corpus(tmp_path):
    repo_root = tmp_path
    _build_fixture(repo_root)

    corpus = corpus_loader.load_corpus(repo_root)
    try:
        components = field(corpus, "components")
        assert "foo" in components
        comp = components["foo"]

        root = field(comp, "root")
        assert root is not None
        assert field(root, "frontmatter") == {
            "id": "comp-foo",
            "owners": ["team-a"],
            "sealed": True,
            "source_path": "legacy/foo/",
        }
        assert field(root, "body") == "# Foo"
        assert not field(root, "body").endswith("\n")
        assert field(root, "doc_id") == "comp-foo"
        assert field(root, "doc_type") == "component-root"

        requirements = field(comp, "requirements")
        assert set(requirements.keys()) == {"R-FOO-001"}
        assert field(requirements["R-FOO-001"], "doc_type") == "component-requirement"
        assert field(requirements["R-FOO-001"], "doc_id") == "R-FOO-001"

        acceptance = field(comp, "acceptance")
        assert set(acceptance.keys()) == {"AC-FOO-001"}
        assert field(acceptance["AC-FOO-001"], "doc_type") == "component-acceptance"
        assert field(acceptance["AC-FOO-001"], "doc_id") == "AC-FOO-001"

        interface_data = field(comp, "interface_data")
        assert set(interface_data.keys()) == {"Thing"}
        assert field(interface_data["Thing"], "doc_type") == "component-interface-data"

        lib = field(comp, "interface_library")
        assert lib is not None
        assert field(lib, "doc_type") == "component-interface-library"
        assert field(comp, "interface_cli") is None

        constraints = field(comp, "constraints")
        assert constraints is not None
        assert field(constraints, "doc_type") == "component-constraints"

        docs = _docs_list(corpus)
        by_rel = {}
        for d in docs:
            rel = field(d, "rel_path")
            assert isinstance(rel, str)
            assert not Path(rel).is_absolute()
            assert "\\" not in rel
            p = Path(field(d, "path"))
            assert p.is_absolute()
            assert p.resolve() == (Path(repo_root) / rel).resolve()
            by_rel[rel] = d

        expected_types = {
            "specs/components/foo/component.md": "component-root",
            "specs/components/foo/requirements/R-FOO-001.md": "component-requirement",
            "specs/components/foo/acceptance/AC-FOO-001.md": "component-acceptance",
            "specs/components/foo/interface/library.md": "component-interface-library",
            "specs/components/foo/interface/data/Thing.md": "component-interface-data",
            "specs/components/foo/constraints.md": "component-constraints",
            "specs/decisions/D200.md": "decision",
        }
        assert set(by_rel.keys()) == set(expected_types.keys())
        for rel, dtype in expected_types.items():
            assert field(by_rel[rel], "doc_type") == dtype

        for rel in by_rel:
            assert not rel.endswith("README.md")
            assert rel != "specs/glossary.md"

        id_index = field(corpus, "id_index")
        assert "comp-foo" in id_index
        assert "D200" in id_index

        glossary_defs = field(corpus, "glossary_defs")
        assert glossary_defs.get("widget") == "a part."

        glossary_files = [Path(p) for p in field(corpus, "glossary_files")]
        glossary_path = (Path(repo_root) / "specs" / "glossary.md").resolve()
        assert any(p.is_absolute() and p.resolve() == glossary_path for p in glossary_files)
        for p in glossary_files:
            assert p.is_absolute()
    finally:
        graph = None
        try:
            graph = field(corpus, "graph")
        except Exception:
            graph = None
        if graph is not None and hasattr(graph, "close"):
            try:
                graph.close()
            except Exception:
                pass