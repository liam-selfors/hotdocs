import os
from pathlib import Path

import corpus_loader


def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _iter_docs(docs):
    if isinstance(docs, dict):
        return list(docs.values())
    return list(docs or [])


def _build_fixture(repo_root: Path):
    specs = repo_root / "specs"

    glossary = _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** — a part.\n",
    )

    comp_dir = specs / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "# Foo\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do a thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nfoo() -> None\n```\n",
    )
    _write(
        comp_dir / "interface" / "data" / "Thing.md",
        "# `Thing`\n\nA thing.\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    _write(
        comp_dir / "README.md",
        "# Foo readme\n",
    )

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

    # Fake graph-query-engine dependency, flat-module shape, matching
    # load_views(con, repo_root) -> None.
    log_path = repo_root / "fake_gqe_calls.log"
    _write(
        repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py",
        "from pathlib import Path\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def load_views(con, repo_root):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('load_views ' + str(repo_root) + '\\n')\n"
        "    return None\n",
    )

    return glossary


def test_ac_corpus_001_load_corpus_builds_corpus_per_contract(tmp_path):
    repo_root = tmp_path.resolve()
    glossary = _build_fixture(repo_root)

    corpus = corpus_loader.load_corpus(repo_root)
    try:
        components = _get(corpus, "components")
        assert components is not None
        foo = components["foo"] if isinstance(components, dict) else None
        assert foo is not None, "components must be keyed by directory name 'foo'"

        # Root doc frontmatter and body
        root = _get(foo, "root")
        assert root is not None
        assert _get(root, "frontmatter") == {
            "id": "comp-foo",
            "owners": ["team-a"],
            "sealed": True,
            "source_path": "legacy/foo/",
        }
        assert _get(root, "body") == "# Foo"
        assert _get(root, "doc_type") == "component-root"
        assert _get(root, "doc_id") == "comp-foo"

        # Requirements keyed by doc_id
        requirements = _get(foo, "requirements")
        assert isinstance(requirements, dict)
        assert list(requirements.keys()) == ["R-FOO-001"]
        req = requirements["R-FOO-001"]
        assert _get(req, "doc_type") == "component-requirement"
        assert _get(req, "doc_id") == "R-FOO-001"

        # Acceptance keyed by doc_id
        acceptance = _get(foo, "acceptance")
        assert isinstance(acceptance, dict)
        assert list(acceptance.keys()) == ["AC-FOO-001"]
        ac = acceptance["AC-FOO-001"]
        assert _get(ac, "doc_type") == "component-acceptance"
        assert _get(ac, "doc_id") == "AC-FOO-001"

        # interface_data keyed by stem
        interface_data = _get(foo, "interface_data")
        assert isinstance(interface_data, dict)
        assert list(interface_data.keys()) == ["Thing"]
        assert _get(interface_data["Thing"], "doc_type") == "component-interface-data"

        # interface_library and constraints
        lib = _get(foo, "interface_library")
        assert lib is not None
        assert _get(lib, "doc_type") == "component-interface-library"
        assert _get(foo, "interface_cli") is None

        constraints = _get(foo, "constraints")
        assert constraints is not None
        assert _get(constraints, "doc_type") == "component-constraints"

        # Every Doc: absolute path, relative rel_path; no README/glossary docs
        docs = _iter_docs(_get(corpus, "docs"))
        assert docs, "corpus.docs must not be empty"
        rel_paths = []
        for doc in docs:
            path = _get(doc, "path")
            rel_path = _get(doc, "rel_path")
            assert isinstance(path, Path), f"path must be a Path, got {type(path)!r}"
            assert path.is_absolute(), f"path not absolute: {path}"
            assert isinstance(rel_path, str)
            assert not os.path.isabs(rel_path), f"rel_path not relative: {rel_path}"
            assert "\\" not in rel_path
            assert path.resolve() == (repo_root / rel_path).resolve()
            rel_paths.append(rel_path)

        assert "specs/glossary.md" not in rel_paths
        assert not any(rp.split("/")[-1] == "README.md" for rp in rel_paths)

        expected = {
            "specs/components/foo/component.md": "component-root",
            "specs/components/foo/requirements/R-FOO-001.md": "component-requirement",
            "specs/components/foo/acceptance/AC-FOO-001.md": "component-acceptance",
            "specs/components/foo/interface/library.md": "component-interface-library",
            "specs/components/foo/interface/data/Thing.md": "component-interface-data",
            "specs/components/foo/constraints.md": "component-constraints",
            "specs/decisions/D200.md": "decision",
        }
        by_rel = {_get(d, "rel_path"): d for d in docs}
        assert set(by_rel.keys()) == set(expected.keys())
        for rp, dtype in expected.items():
            assert _get(by_rel[rp], "doc_type") == dtype, rp

        decision_doc = by_rel["specs/decisions/D200.md"]
        assert _get(decision_doc, "doc_id") == "D200"

        # id_index
        id_index = _get(corpus, "id_index")
        assert id_index is not None
        assert "comp-foo" in id_index
        assert "D200" in id_index

        # glossary_defs
        glossary_defs = _get(corpus, "glossary_defs")
        assert isinstance(glossary_defs, dict)
        assert glossary_defs.get("widget") == "a part."

        # glossary_files
        glossary_files = list(_get(corpus, "glossary_files") or [])
        assert glossary_files, "glossary_files must list the glossary"
        for gf in glossary_files:
            assert Path(gf).is_absolute()
        assert glossary.resolve() in [Path(gf).resolve() for gf in glossary_files]
    finally:
        graph = _get(corpus, "graph")
        close = getattr(graph, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass