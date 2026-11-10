from pathlib import Path

import corpus_loader


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


FAKE_GRAPH_QUERY_ENGINE = '''
def load_views(con, repo_root):
    con.execute(
        "CREATE OR REPLACE VIEW nodes AS SELECT "
        "CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS title, "
        "CAST(NULL AS VARCHAR) AS status, CAST(NULL AS VARCHAR) AS kind, "
        "CAST(NULL AS VARCHAR) AS owner_component_id WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW edges AS SELECT "
        "CAST(NULL AS VARCHAR) AS source_id, CAST(NULL AS VARCHAR) AS target_id, "
        "CAST(NULL AS VARCHAR) AS edge_type WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW component_docs AS SELECT "
        "CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS title, "
        "CAST(NULL AS VARCHAR) AS status, CAST(NULL AS VARCHAR) AS body WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW component_context AS SELECT "
        "CAST(NULL AS VARCHAR) AS component_id, CAST(NULL AS VARCHAR) AS purpose WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW component_provenance AS SELECT "
        "CAST(NULL AS VARCHAR) AS component_id, CAST(NULL AS VARCHAR) AS spec_bundle_hash, "
        "CAST(NULL AS BOOLEAN) AS provenance_hit WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW component_size AS SELECT "
        "CAST(NULL AS VARCHAR) AS component_id, CAST(NULL AS BIGINT) AS word_count WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW decision_lineage AS SELECT "
        "CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS last_ratified_commit WHERE FALSE"
    )
'''


def _build_repo_root(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"

    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** \u2014 a part.\n",
    )

    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "# Foo\n",
    )

    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 Foo must do something.\n",
    )

    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\n\nFoo does something.\n",
    )

    _write(
        repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
        "# Library\n\nSome library doc.\n",
    )

    _write(
        repo_root / "specs" / "components" / "foo" / "interface" / "data" / "Thing.md",
        "# Thing\n\nSome data doc.\n",
    )

    _write(
        repo_root / "specs" / "components" / "foo" / "constraints.md",
        "# Constraints\n\nNone.\n",
    )

    _write(
        repo_root / "specs" / "components" / "foo" / "README.md",
        "# Foo component\n\nInternal readme, not part of the doc corpus.\n",
    )

    _write(
        repo_root / "specs" / "decisions" / "D200.md",
        "---\n"
        "id: D200\n"
        "title: Some Decision\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "Some decision body.\n",
    )

    _write(
        repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py",
        FAKE_GRAPH_QUERY_ENGINE,
    )

    return repo_root


def test_ac_corpus_001(tmp_path):
    repo_root = _build_repo_root(tmp_path)

    corpus = corpus_loader.load_corpus(repo_root)

    components = _field(corpus, "components")
    foo = components["foo"] if not isinstance(components, dict) else components.get("foo")
    assert foo is not None

    root = _field(foo, "root")
    assert root is not None

    frontmatter = _field(root, "frontmatter")
    assert frontmatter == {
        "id": "comp-foo",
        "owners": ["team-a"],
        "sealed": True,
        "source_path": "legacy/foo/",
    }

    body = _field(root, "body")
    assert body == "# Foo"

    assert _field(root, "doc_id") == "comp-foo"
    assert _field(root, "doc_type") == "component-root"

    requirements = _field(foo, "requirements")
    assert "R-FOO-001" in requirements

    acceptance = _field(foo, "acceptance")
    assert "AC-FOO-001" in acceptance

    interface_data = _field(foo, "interface_data")
    assert "Thing" in interface_data

    req_doc = requirements["R-FOO-001"] if isinstance(requirements, dict) else requirements.get("R-FOO-001")
    assert _field(req_doc, "doc_type") == "component-requirement"
    assert _field(req_doc, "doc_id") == "R-FOO-001"

    acc_doc = acceptance["AC-FOO-001"] if isinstance(acceptance, dict) else acceptance.get("AC-FOO-001")
    assert _field(acc_doc, "doc_type") == "component-acceptance"
    assert _field(acc_doc, "doc_id") == "AC-FOO-001"

    thing_doc = interface_data["Thing"] if isinstance(interface_data, dict) else interface_data.get("Thing")
    assert _field(thing_doc, "doc_type") == "component-interface-data"

    constraints_doc = _field(foo, "constraints")
    assert _field(constraints_doc, "doc_type") == "component-constraints"

    docs = _field(corpus, "docs")
    docs_by_rel = {}
    for d in docs:
        rel = _field(d, "rel_path")
        docs_by_rel[rel] = d

        path_val = _field(d, "path")
        assert Path(str(path_val)).is_absolute()

        assert rel is not None
        assert not Path(rel).is_absolute()
        assert "\\" not in rel

    expected_rel_types = {
        "specs/components/foo/component.md": "component-root",
        "specs/components/foo/requirements/R-FOO-001.md": "component-requirement",
        "specs/components/foo/acceptance/AC-FOO-001.md": "component-acceptance",
        "specs/components/foo/interface/library.md": "component-interface-library",
        "specs/components/foo/interface/data/Thing.md": "component-interface-data",
        "specs/components/foo/constraints.md": "component-constraints",
        "specs/decisions/D200.md": "decision",
    }
    for rel, expected_type in expected_rel_types.items():
        assert rel in docs_by_rel, rel
        assert _field(docs_by_rel[rel], "doc_type") == expected_type

    assert "specs/components/foo/README.md" not in docs_by_rel
    assert "specs/glossary.md" not in docs_by_rel

    d200_doc = docs_by_rel["specs/decisions/D200.md"]
    assert _field(d200_doc, "doc_id") == "D200"

    id_index = _field(corpus, "id_index")
    assert "comp-foo" in id_index
    assert "D200" in id_index

    glossary_defs = _field(corpus, "glossary_defs")
    assert glossary_defs.get("widget") == "a part."

    glossary_files = _field(corpus, "glossary_files")
    expected_glossary_path = (repo_root / "specs" / "glossary.md").resolve()
    found = any(
        Path(str(p)).resolve() == expected_glossary_path for p in glossary_files
    )
    assert found