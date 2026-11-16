import corpus_loader

from pathlib import Path


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
        "**R-FOO-001** — `foo()` MUST return None.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When foo() runs\n"
        "Then it returns None\n"
        "```\n",
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
    _write(comp / "README.md", "# Foo readme\n\nNot a spec doc.\n")

    _write(
        specs / "decisions" / "D200.md",
        "---\n"
        "id: D200\n"
        "title: Decision two hundred\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "# D200\n"
        "\n"
        "A decision.\n",
    )

    # Fake graph-query-engine dependency, matching its documented signature
    # load_views(con, repo_root) -> None.
    _write(
        repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py",
        "def load_views(con, repo_root):\n"
        "    return None\n",
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

        # Root doc frontmatter and body
        root = field(foo, "root")
        assert root is not None
        assert field(root, "frontmatter") == {
            "id": "comp-foo",
            "owners": ["team-a"],
            "sealed": True,
            "source_path": "legacy/foo/",
        }
        assert field(root, "body") == "# Foo"
        assert not field(root, "body").endswith("\n")
        assert field(root, "doc_type") == "component-root"
        assert field(root, "doc_id") == "comp-foo"

        # Keyed dicts
        requirements = field(foo, "requirements")
        acceptance = field(foo, "acceptance")
        interface_data = field(foo, "interface_data")
        assert set(requirements.keys()) == {"R-FOO-001"}
        assert set(acceptance.keys()) == {"AC-FOO-001"}
        assert set(interface_data.keys()) == {"Thing"}

        # doc_types per Corpus.md
        assert field(requirements["R-FOO-001"], "doc_type") == "component-requirement"
        assert field(acceptance["AC-FOO-001"], "doc_type") == "component-acceptance"
        assert field(interface_data["Thing"], "doc_type") == "component-interface-data"
        lib = field(foo, "interface_library")
        assert lib is not None
        assert field(lib, "doc_type") == "component-interface-library"
        constraints = field(foo, "constraints")
        assert constraints is not None
        assert field(constraints, "doc_type") == "component-constraints"

        # id_index
        id_index = field(corpus, "id_index")
        assert "comp-foo" in id_index
        assert "D200" in id_index
        assert field(id_index["D200"], "doc_type") == "decision"

        # Every doc: absolute path, relative rel_path; no README/glossary docs
        docs = _docs_list(field(corpus, "docs"))
        rel_paths = set()
        for doc in docs:
            p = field(doc, "path")
            rp = field(doc, "rel_path")
            assert isinstance(p, Path)
            assert p.is_absolute()
            assert isinstance(rp, str)
            assert not Path(rp).is_absolute()
            assert not rp.startswith("/")
            assert "\\" not in rp
            assert Path(rp).name != "README.md"
            assert rp != "specs/glossary.md"
            rel_paths.add(rp)

        assert rel_paths == {
            "specs/components/foo/component.md",
            "specs/components/foo/requirements/R-FOO-001.md",
            "specs/components/foo/acceptance/AC-FOO-001.md",
            "specs/components/foo/interface/library.md",
            "specs/components/foo/interface/data/Thing.md",
            "specs/components/foo/constraints.md",
            "specs/decisions/D200.md",
        }

        # Glossary fields
        glossary_defs = field(corpus, "glossary_defs")
        assert glossary_defs.get("widget") == "a part."
        glossary_files = list(field(corpus, "glossary_files"))
        glossary_path = (repo_root / "specs" / "glossary.md").resolve()
        assert any(
            Path(g).is_absolute() and Path(g).resolve() == glossary_path
            for g in glossary_files
        )
    finally:
        try:
            graph = field(corpus, "graph")
            if graph is not None:
                graph.close()
        except Exception:
            pass