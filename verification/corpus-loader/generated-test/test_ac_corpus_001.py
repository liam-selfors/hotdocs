# hotdocs-criterion: sha256:09fbb7199e6bbb7e756146cd7327dab9ed8791eea7774f53e30ea8ad203456b3
import os
from pathlib import Path

import corpus_loader


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path, log_path: Path) -> None:
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary.\n"
        "\n"
        "- **Widget** — a part.\n",
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
        "# R-FOO-001\n\n**R-FOO-001** — The foo MUST do a thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "Given a thing\nWhen it runs\nThen it works\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndo_thing() -> None\n```\n",
    )
    _write(
        comp / "interface" / "data" / "Thing.md",
        "# `Thing`\n\nA thing.\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(comp / "README.md", "# Foo readme\n")

    _write(
        specs / "decisions" / "D200.md",
        "---\n"
        "id: D200\n"
        "title: A decision\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "# D200\n\nWe decided.\n",
    )

    # Fake graph-query-engine dependency, flat-module shape, matching the
    # documented load_views(con, repo_root) -> None contract.
    fake_dir = repo_root / "gen" / "graph-query-engine"
    _write(
        fake_dir / "graph_query_engine.py",
        "from pathlib import Path\n"
        "\n"
        f"_LOG = {str(log_path)!r}\n"
        "\n"
        "\n"
        "def load_views(con, repo_root):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('load_views ' + str(repo_root) + '\\n')\n"
        "    return None\n",
    )


def _docs_list(docs):
    if isinstance(docs, dict):
        return list(docs.values())
    return list(docs)


def test_ac_corpus_001(tmp_path):
    base = tmp_path.resolve()
    repo_root = base / "repo"
    repo_root.mkdir()
    log_path = base / "fake_calls.log"
    _build_fixture(repo_root, log_path)

    corpus = corpus_loader.load_corpus(repo_root)
    try:
        components = _get(corpus, "components")
        assert components is not None
        assert "foo" in components
        foo = components["foo"]

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
        assert not _get(root, "body").endswith("\n")
        assert _get(root, "doc_type") == "component-root"
        assert _get(root, "doc_id") == "comp-foo"

        # Requirements / acceptance / interface_data keys
        requirements = _get(foo, "requirements")
        assert list(requirements.keys()) == ["R-FOO-001"]
        req = requirements["R-FOO-001"]
        assert _get(req, "doc_type") == "component-requirement"
        assert _get(req, "doc_id") == "R-FOO-001"

        acceptance = _get(foo, "acceptance")
        assert list(acceptance.keys()) == ["AC-FOO-001"]
        ac = acceptance["AC-FOO-001"]
        assert _get(ac, "doc_type") == "component-acceptance"
        assert _get(ac, "doc_id") == "AC-FOO-001"

        interface_data = _get(foo, "interface_data")
        assert list(interface_data.keys()) == ["Thing"]
        assert _get(interface_data["Thing"], "doc_type") == "component-interface-data"

        library = _get(foo, "interface_library")
        assert library is not None
        assert _get(library, "doc_type") == "component-interface-library"

        constraints = _get(foo, "constraints")
        assert constraints is not None
        assert _get(constraints, "doc_type") == "component-constraints"

        assert _get(foo, "interface_cli") is None

        # Docs: exact set, types, absolute paths, relative rel_paths
        docs = _docs_list(_get(corpus, "docs"))
        expected_types = {
            "specs/components/foo/component.md": "component-root",
            "specs/components/foo/requirements/R-FOO-001.md": "component-requirement",
            "specs/components/foo/acceptance/AC-FOO-001.md": "component-acceptance",
            "specs/components/foo/interface/library.md": "component-interface-library",
            "specs/components/foo/interface/data/Thing.md": "component-interface-data",
            "specs/components/foo/constraints.md": "component-constraints",
            "specs/decisions/D200.md": "decision",
        }
        seen = {}
        for doc in docs:
            path = _get(doc, "path")
            rel_path = _get(doc, "rel_path")
            assert isinstance(rel_path, str)
            assert Path(path).is_absolute(), path
            assert not os.path.isabs(rel_path), rel_path
            assert "\\" not in rel_path
            assert Path(path).resolve() == (repo_root / rel_path).resolve()
            seen[rel_path] = _get(doc, "doc_type")

        assert seen == expected_types
        for rel_path in seen:
            assert not rel_path.endswith("README.md")
            assert rel_path != "specs/glossary.md"

        # id_index
        id_index = _get(corpus, "id_index")
        assert "comp-foo" in id_index
        assert "D200" in id_index

        # Glossary
        glossary_defs = _get(corpus, "glossary_defs")
        assert glossary_defs.get("widget") == "a part."

        glossary_files = list(_get(corpus, "glossary_files"))
        glossary_abs = (repo_root / "specs" / "glossary.md").resolve()
        assert all(Path(p).is_absolute() for p in glossary_files)
        assert glossary_abs in [Path(p).resolve() for p in glossary_files]
    finally:
        graph = _get(corpus, "graph")
        close = getattr(graph, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass