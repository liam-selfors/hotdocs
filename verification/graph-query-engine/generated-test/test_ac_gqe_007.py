# hotdocs-criterion: sha256:535bedc36ef440b2d97e5f4cd07549090f6a779f4d1d4ade612112a8218e47fa
"""AC-GQE-007: load_views is idempotent on the same DuckDB connection.

Given a DuckDB connection with load_views already called once
When load_views is called again on the same connection
Then it succeeds without error and every view still returns the same
  results as the first call
"""

from pathlib import Path

import duckdb

import graph_query_engine


VIEWS = [
    "nodes",
    "edges",
    "component_docs",
    "component_context",
    "component_provenance",
    "component_size",
    "bundle_size",
    "decision_lineage",
]


def _write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _frontmatter(lines):
    return "---\n" + "".join(line + "\n" for line in lines) + "---\n"


def _build_fixture(root):
    _write(
        root,
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
        + "\n"
        + "# Foo\n"
        + "\n"
        + "one two three\n",
    )
    _write(
        root,
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
        + "\n"
        + "# Bar\n",
    )
    _write(
        root,
        "specs/components/foo/requirements/R-FOO-001.md",
        "# R-FOO-001\n\nfoo MUST work.\n",
    )
    _write(
        root,
        "specs/components/foo/requirements/R-FOO-002.md",
        "# R-FOO-002\n\nfoo MUST stop.\n",
    )
    _write(
        root,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )
    _write(
        root,
        "specs/components/foo/acceptance/AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: generated-test\n",
    )
    _write(
        root,
        "specs/components/foo/interface/guarantees/G-FOO-001.md",
        "# G-FOO-001\n\nfoo never fails.\n",
    )
    _write(
        root,
        "specs/product/x.md",
        _frontmatter(["id: P-X", "title: X", "status: draft", "owners: [team]"])
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
        _frontmatter(["id: VAR-X", "title: V", "status: draft", "owners: [team]"])
        + "# V\n",
    )
    _write(
        root,
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
        root,
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
        _write(root, d + "/README.md", "# Readme\n\nNotes.\n")


def _snapshot(con):
    result = {}
    for view in VIEWS:
        cur = con.execute("SELECT * FROM " + view)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        rows_sorted = sorted(rows, key=repr)
        result[view] = (columns, rows_sorted)
    return result


def test_ac_gqe_007_load_views_twice_is_idempotent(tmp_path):
    repo_root = Path(tmp_path).resolve()
    _build_fixture(repo_root)

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")

        graph_query_engine.load_views(con, repo_root)
        first = _snapshot(con)

        # Second call on the same connection must not raise.
        graph_query_engine.load_views(con, repo_root)
        second = _snapshot(con)

        for view in VIEWS:
            assert view in first
            assert view in second
            first_cols, first_rows = first[view]
            second_cols, second_rows = second[view]
            assert first_cols == second_cols, view + ": columns changed"
            assert first_rows == second_rows, view + ": rows changed"

        # Sanity: the corpus is actually seen, so the comparison is meaningful.
        assert len(first["nodes"][1]) > 0
        assert len(first["edges"][1]) > 0
        assert len(first["component_docs"][1]) == 2
    finally:
        con.close()