# hotdocs-criterion: sha256:6499ca427121f4d881312d2c5f9763c42fe2258f22b053c18ab9ffc5ab573482
"""AC-GQE-010 (covers R-GQE-002): the decision arms of the `edges` view read
only a decision's frontmatter block, never its prose, and `builds_on`
yields one row per flow-style list entry."""

from pathlib import Path

import duckdb
import pytest

import graph_query_engine


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _frontmatter(lines):
    return "---\n" + "\n".join(lines) + "\n---\n"


def _build_base_fixture(repo_root):
    _write(
        repo_root,
        "specs/components/foo/component.md",
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
        repo_root,
        "specs/components/bar/component.md",
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
        repo_root,
        "specs/components/foo/requirements/R-FOO-001.md",
        "# R-FOO-001\n\nfoo MUST work.\n",
    )
    _write(
        repo_root,
        "specs/components/foo/requirements/R-FOO-002.md",
        "# R-FOO-002\n\nfoo MUST stop.\n",
    )
    _write(
        repo_root,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )
    _write(
        repo_root,
        "specs/components/foo/interface/guarantees/G-FOO-001.md",
        "# G-FOO-001\n\nfoo never fails.\n",
    )
    _write(
        repo_root,
        "specs/product/x.md",
        _frontmatter(["id: P-X", "title: X", "status: draft", "owners: [team]"])
        + "# X\n\n### CS-X-001\nCovers: P-X\n\n### CS-X-002\nCovers: P-X\n",
    )
    _write(
        repo_root,
        "specs/vars/x.md",
        _frontmatter(["id: VAR-X", "title: V", "status: draft", "owners: [team]"])
        + "# V\n",
    )
    _write(
        repo_root,
        "specs/decisions/D1.md",
        _frontmatter(
            [
                "id: D1",
                "title: One",
                "status: ratified",
                "owners: [team]",
                "last_ratified_commit: 0000000",
            ]
        )
        + "# D1\n",
    )
    _write(
        repo_root,
        "specs/decisions/D2.md",
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
        + "# D2\n",
    )
    for d in ("specs/product", "specs/vars", "specs/decisions"):
        _write(repo_root, d + "/README.md", "# Readme\n\nNotes.\n")


def _build_fixture(repo_root):
    _build_base_fixture(repo_root)
    # A decision whose prose quotes the fields at line starts, but whose
    # frontmatter declares neither.
    _write(
        repo_root,
        "specs/decisions/D3.md",
        _frontmatter(["id: D3", "title: Three", "status: draft", "owners: [team]"])
        + "# D3\n\n"
        + "A prior draft of this record carried these lines:\n\n"
        + "supersedes: D1\n"
        + "builds_on: [D2]\n\n"
        + "Neither is declared here; they are only quoted.\n",
    )
    # A decision whose frontmatter declares builds_on: [D1, D2].
    _write(
        repo_root,
        "specs/decisions/D4.md",
        _frontmatter(
            [
                "id: D4",
                "title: Four",
                "status: draft",
                "owners: [team]",
                "builds_on: [D1, D2]",
            ]
        )
        + "# D4\n",
    )


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


def test_prose_quoted_fields_produce_no_decision_edges(con):
    rows = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE source_id = 'D3' AND edge_type IN ('supersedes', 'builds_on')"
    ).fetchall()
    assert rows == []


def test_builds_on_list_yields_exactly_one_row_per_entry(con):
    rows = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE source_id = 'D4' ORDER BY target_id, edge_type"
    ).fetchall()
    assert [tuple(r) for r in rows] == [
        ("D4", "D1", "builds_on"),
        ("D4", "D2", "builds_on"),
    ]