# hotdocs-criterion: sha256:aefe9120909ff6ff02a493886d2b6ed5a070ce39ecfbe5fdd16d16dac86aa6d6
"""AC-GQE-007: load_views is idempotent on the same DuckDB connection.

Given a DuckDB connection with load_views already called once,
when load_views is called again on the same connection,
then it succeeds without error and every view still returns the same
results as the first call.
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
    "decision_lineage",
]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _frontmatter(lines):
    return "---\n" + "".join(line + "\n" for line in lines) + "---\n"


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
        + "\n"
        + "# Foo\n"
        + "\n"
        + "one two three\n",
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
        + "\n"
        + "# Bar\n",
    )
    _write(
        specs / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n" + "\n" + "foo MUST work.\n",
    )
    _write(
        specs / "components" / "foo" / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n" + "\n" + "foo MUST stop.\n",
    )
    _write(
        specs / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n" + "\n" + "Covers: R-FOO-001\n" + "Kind: generated-test\n",
    )
    _write(
        specs / "components" / "foo" / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n" + "\n" + "Covers: R-FOO-002\n" + "Kind: generated-test\n",
    )
    _write(
        specs / "components" / "foo" / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n" + "\n" + "foo never fails.\n",
    )
    _write(
        specs / "product" / "x.md",
        _frontmatter(["id: P-X", "title: X", "status: draft", "owners: [team]"])
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
        _frontmatter(["id: VAR-X", "title: V", "status: draft", "owners: [team]"])
        + "\n"
        + "# V\n",
    )
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
        + "\n"
        + "# D1\n",
    )
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
        + "\n"
        + "# D2\n",
    )
    for sub in ("product", "vars", "decisions"):
        _write(specs / sub / "README.md", "# Readme\n" + "\n" + "Notes.\n")


def _snapshot(con):
    snap = {}
    for view in VIEWS:
        cur = con.execute("SELECT * FROM " + view)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        snap[view] = (columns, sorted(repr(r) for r in rows))
    return snap


def test_load_views_twice_is_idempotent(tmp_path):
    repo_root = Path(tmp_path).resolve()
    _build_fixture(repo_root)

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")

        graph_query_engine.load_views(con, repo_root)
        first = _snapshot(con)

        # Sanity: the first load produced real data for the core views,
        # so the comparison below is meaningful.
        assert len(first["nodes"][1]) > 0
        assert len(first["edges"][1]) > 0
        assert len(first["component_docs"][1]) == 2
        assert len(first["component_context"][1]) == 2
        assert len(first["component_size"][1]) == 2
        assert len(first["decision_lineage"][1]) == 2

        # Second call on the same connection must not raise.
        result = graph_query_engine.load_views(con, repo_root)
        assert result is None

        second = _snapshot(con)

        for view in VIEWS:
            assert view in second, "view missing after second load: " + view
            assert second[view][0] == first[view][0], (
                "columns changed for view " + view
            )
            assert second[view][1] == first[view][1], (
                "rows changed for view " + view
            )
    finally:
        con.close()