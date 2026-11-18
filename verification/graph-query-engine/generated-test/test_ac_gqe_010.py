# hotdocs-criterion: sha256:76fd641519c1926ac386c647cca0ec4a6f40f6298261b972d58b12b6705e5c2e
"""AC-GQE-010 (covers R-GQE-002): the decision arms of `edges` read only a
decision's frontmatter block, and a flow-style `builds_on` list yields one
row per entry."""

from pathlib import Path

import duckdb
import pytest

import graph_query_engine


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _build_corpus(repo_root):
    specs = repo_root / "specs"

    _write(
        specs / "components" / "foo" / "component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [team]\n"
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
        specs / "components" / "bar" / "component.md",
        "---\n"
        + "id: comp-bar\n"
        + "title: Bar\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "realizes: [P-X]\n"
        + "---\n"
        + "\n"
        + "# Bar\n",
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
        specs / "components" / "foo" / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: generated-test\n",
    )
    _write(
        specs / "components" / "foo" / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n\nfoo never fails.\n",
    )
    _write(
        specs / "product" / "x.md",
        "---\n"
        + "id: P-X\n"
        + "title: X\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "\n"
        + "# X\n"
        + "\n"
        + "### CS-X-001\n"
        + "Covers: P-X\n"
        + "\n"
        + "### CS-X-002\n"
        + "Covers: P-X\n",
    )
    _write(
        specs / "vars" / "x.md",
        "---\n"
        + "id: VAR-X\n"
        + "title: V\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "\n"
        + "# V\n",
    )
    _write(
        specs / "decisions" / "D1.md",
        "---\n"
        + "id: D1\n"
        + "title: One\n"
        + "status: ratified\n"
        + "owners: [team]\n"
        + "last_ratified_commit: 0000000\n"
        + "---\n"
        + "\n"
        + "# D1\n",
    )
    _write(
        specs / "decisions" / "D2.md",
        "---\n"
        + "id: D2\n"
        + "title: Two\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "supersedes: D1\n"
        + "builds_on: [D1]\n"
        + "---\n"
        + "\n"
        + "# D2\n",
    )
    # D3: prose quotes both fields (inline and at line starts), frontmatter
    # declares neither.
    _write(
        specs / "decisions" / "D3.md",
        "---\n"
        + "id: D3\n"
        + "title: Three\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "\n"
        + "# D3\n"
        + "\n"
        + "An earlier draft of this record carried `supersedes: D1` and\n"
        + "`builds_on: [D2]`, quoted here only as history:\n"
        + "\n"
        + "supersedes: D1\n"
        + "builds_on: [D2]\n",
    )
    # D4: frontmatter declares builds_on with two entries.
    _write(
        specs / "decisions" / "D4.md",
        "---\n"
        + "id: D4\n"
        + "title: Four\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "builds_on: [D1, D2]\n"
        + "---\n"
        + "\n"
        + "# D4\n",
    )
    for sub in ("product", "vars", "decisions"):
        _write(specs / sub / "README.md", "# Readme\n\nNotes.\n")


@pytest.fixture
def con(tmp_path):
    repo_root = Path(tmp_path) / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    connection = duckdb.connect()
    connection.execute("INSTALL yaml FROM community")
    connection.execute("LOAD yaml")
    graph_query_engine.load_views(connection, repo_root)
    try:
        yield connection
    finally:
        connection.close()


def test_prose_quoted_fields_produce_no_decision_edges(con):
    rows = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE source_id = 'D3' AND edge_type IN ('supersedes', 'builds_on')"
    ).fetchall()
    assert rows == []


def test_builds_on_list_yields_exactly_one_row_per_entry(con):
    rows = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges WHERE source_id = 'D4'"
    ).fetchall()
    assert sorted(rows) == [
        ("D4", "D1", "builds_on"),
        ("D4", "D2", "builds_on"),
    ]
    assert len(rows) == 2