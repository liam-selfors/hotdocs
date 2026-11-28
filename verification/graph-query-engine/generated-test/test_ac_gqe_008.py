# hotdocs-criterion: sha256:334969fd2293ce2a958d2be48c926dfbf2592a83709fb8b2b8ceca4bf37af48a
"""AC-GQE-008: decision_lineage returns id and last_ratified_commit only,
with NULL (not '') for a decision lacking last_ratified_commit."""

from pathlib import Path

import duckdb
import pytest

import graph_query_engine


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _frontmatter(lines):
    return "---\n" + "\n".join(lines) + "\n---\n"


def _build_fixture(repo_root):
    specs = repo_root / "specs"

    _write(
        specs / "components" / "foo" / "component.md",
        _frontmatter(
            [
                "id: comp-foo",
                "title: Foo",
                "status: draft",
                "owners: [team]",
                "depends_on: [comp-bar]",
                "realizes: [P-X]",
                "uses_var: [VAR-X]",
                "depends_on_guarantees: [G-BAR-001]",
            ]
        )
        + "\n# Foo\n\none two three\n",
    )
    _write(
        specs / "components" / "bar" / "component.md",
        _frontmatter(
            [
                "id: comp-bar",
                "title: Bar",
                "status: draft",
                "owners: [team]",
                "realizes: [P-X]",
            ]
        )
        + "\n# Bar\n",
    )
    _write(
        specs / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\nfoo MUST work.\n",
    )
    _write(
        specs / "components" / "foo" / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\nfoo MUST stop.\n",
    )
    _write(
        specs / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )
    _write(
        specs / "components" / "foo" / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n\nfoo never fails.\n",
    )
    _write(
        specs / "product" / "x.md",
        _frontmatter(["id: P-X", "title: X", "status: draft", "owners: [team]"])
        + "\n# X\n\n### CS-X-001\nCovers: P-X\n\n### CS-X-002\nCovers: P-X\n",
    )
    _write(
        specs / "vars" / "x.md",
        _frontmatter(["id: VAR-X", "title: V", "status: draft", "owners: [team]"])
        + "\n# V\n",
    )
    # D1: ratified, with last_ratified_commit set.
    _write(
        specs / "decisions" / "D1.md",
        _frontmatter(
            [
                "id: D1",
                "title: One",
                "status: ratified",
                "owners: [team]",
                "last_ratified_commit: 0000000",
            ]
        )
        + "\n# D1\n",
    )
    # D2: no last_ratified_commit field at all.
    _write(
        specs / "decisions" / "D2.md",
        _frontmatter(
            [
                "id: D2",
                "title: Two",
                "status: draft",
                "owners: [team]",
                "supersedes: D1",
                "builds_on: [D1]",
            ]
        )
        + "\n# D2\n",
    )
    for sub in ("product", "vars", "decisions"):
        _write(specs / sub / "README.md", "# Readme\n\nNotes.\n")


@pytest.fixture
def con(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    connection = duckdb.connect()
    connection.execute("INSTALL yaml FROM community")
    connection.execute("LOAD yaml")
    graph_query_engine.load_views(connection, repo_root)
    try:
        yield connection
    finally:
        connection.close()


def test_decision_lineage_commit_null_and_columns(con):
    cur = con.execute(
        "SELECT * FROM decision_lineage ORDER BY id"
    )
    column_names = [d[0] for d in cur.description]
    rows = cur.fetchall()

    # The view has no other columns than id and last_ratified_commit.
    assert sorted(column_names) == ["id", "last_ratified_commit"]
    assert len(column_names) == 2

    by_id = {}
    id_idx = column_names.index("id")
    commit_idx = column_names.index("last_ratified_commit")
    for row in rows:
        by_id[row[id_idx]] = row[commit_idx]

    # One row per decision file; the README (no frontmatter) yields none.
    assert len(rows) == 2
    assert set(by_id) == {"D1", "D2"}

    # First decision's last_ratified_commit is the commit it set.
    assert by_id["D1"] == "0000000"

    # Second decision's is NULL, not an empty string.
    assert by_id["D2"] is None
    assert by_id["D2"] != ""

    null_count = con.execute(
        "SELECT count(*) FROM decision_lineage "
        "WHERE id = 'D2' AND last_ratified_commit IS NULL"
    ).fetchone()[0]
    assert null_count == 1

    empty_count = con.execute(
        "SELECT count(*) FROM decision_lineage WHERE last_ratified_commit = ''"
    ).fetchone()[0]
    assert empty_count == 0