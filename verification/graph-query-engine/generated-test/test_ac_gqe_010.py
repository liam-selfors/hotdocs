# hotdocs-criterion: sha256:7fa0247cce126cad4601fa5252ee68f1078db4a1a39aa58cb949ba3a25c0ed5f
from pathlib import Path

import duckdb
import pytest

import graph_query_engine


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _build_corpus(root):
    _write(
        root,
        "specs/components/foo/component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "depends_on: [comp-bar]\n"
        + "realizes: [P-X]\n"
        + "uses_var: [VAR-X]\n"
        + "depends_on_guarantees: [G-BAR-001]\n"
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "one two three\n",
    )
    _write(
        root,
        "specs/components/bar/component.md",
        "---\n"
        + "id: comp-bar\n"
        + "title: Bar\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "sealed: true\n"
        + "source_path: legacy/bar/\n"
        + "realizes: [P-X]\n"
        + "---\n"
        + "\n"
        + "# Bar\n",
    )
    _write(root, "specs/components/foo/requirements/R-FOO-001.md",
           "# R-FOO-001\n\nfoo MUST work.\n")
    _write(root, "specs/components/foo/requirements/R-FOO-002.md",
           "# R-FOO-002\n\nfoo MUST stop.\n")
    _write(root, "specs/components/foo/acceptance/AC-FOO-001.md",
           "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n")
    _write(root, "specs/components/foo/acceptance/AC-FOO-002.md",
           "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: generated-test\n")
    _write(root, "specs/components/foo/interface/guarantees/G-FOO-001.md",
           "# G-FOO-001\n\nfoo never fails.\n")
    _write(
        root,
        "specs/product/x.md",
        "---\n"
        + "id: P-X\n"
        + "title: X\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "# X\n"
        + "\n"
        + "### CS-X-001\n"
        + "Covers: P-X\n"
        + "\n"
        + "### CS-X-002\n"
        + "Covers: P-X\n",
    )
    _write(
        root,
        "specs/vars/x.md",
        "---\n"
        + "id: VAR-X\n"
        + "title: V\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "# V\n",
    )
    _write(
        root,
        "specs/decisions/D1.md",
        "---\n"
        + "id: D1\n"
        + "title: One\n"
        + "status: ratified\n"
        + "owners: [team]\n"
        + "last_ratified_commit: 0000000\n"
        + "---\n"
        + "# D1\n",
    )
    _write(
        root,
        "specs/decisions/D2.md",
        "---\n"
        + "id: D2\n"
        + "title: Two\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "supersedes: D1\n"
        + "builds_on: [D1]\n"
        + "---\n"
        + "# D2\n",
    )
    # A decision whose prose quotes supersedes/builds_on but whose
    # frontmatter declares neither.
    _write(
        root,
        "specs/decisions/D3.md",
        "---\n"
        + "id: D3\n"
        + "title: Three\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "# D3\n"
        + "\n"
        + "This decision quotes another record's frontmatter:\n"
        + "\n"
        + "supersedes: D1\n"
        + "builds_on: [D2]\n"
        + "\n"
        + "Inline too: `supersedes: D1` and `builds_on: [D2]`.\n",
    )
    # A decision whose frontmatter declares builds_on: [D1, D2].
    _write(
        root,
        "specs/decisions/D4.md",
        "---\n"
        + "id: D4\n"
        + "title: Four\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "builds_on: [D1, D2]\n"
        + "---\n"
        + "# D4\n",
    )
    for d in ("specs/product", "specs/vars", "specs/decisions"):
        _write(root, d + "/README.md", "# Readme\n\nNotes.\n")


@pytest.fixture
def con(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    connection = duckdb.connect()
    connection.execute("INSTALL yaml FROM community")
    connection.execute("LOAD yaml")
    graph_query_engine.load_views(connection, repo_root)
    yield connection
    connection.close()


def test_prose_quoted_fields_produce_no_decision_edges(con):
    rows = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE source_id = 'D3' AND edge_type IN ('supersedes', 'builds_on')"
    ).fetchall()
    assert rows == []

    # Sanity: no decision edge anywhere targets as if sourced from D3's prose.
    all_d3 = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges WHERE source_id = 'D3'"
    ).fetchall()
    assert all_d3 == []


def test_frontmatter_builds_on_list_yields_exactly_its_rows(con):
    rows = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges WHERE source_id = 'D4'"
    ).fetchall()
    assert len(rows) == 2
    assert sorted(tuple(r) for r in rows) == [
        ("D4", "D1", "builds_on"),
        ("D4", "D2", "builds_on"),
    ]