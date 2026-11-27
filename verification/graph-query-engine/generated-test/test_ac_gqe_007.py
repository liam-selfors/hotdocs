# hotdocs-criterion: sha256:00d7c6db752e861d95b9dbb932bbd8bebfc00323c6173ff1933a1c03ac1be302
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
    "bundle_size",
    "decision_lineage",
]


def _write(repo_root, rel, lines):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


def _build_fixture(repo_root):
    _write(
        repo_root,
        "specs/components/foo/component.md",
        [
            "---",
            "id: comp-foo",
            "title: Foo",
            "status: draft",
            "owners: [team]",
            "depends_on: [comp-bar]",
            "realizes: [P-X]",
            "uses_var: [VAR-X]",
            "depends_on_guarantees: [G-BAR-001]",
            "---",
            "",
            "# Foo",
            "",
            "one two three",
        ],
    )
    _write(
        repo_root,
        "specs/components/bar/component.md",
        [
            "---",
            "id: comp-bar",
            "title: Bar",
            "status: draft",
            "owners: [team]",
            "realizes: [P-X]",
            "---",
            "",
            "# Bar",
        ],
    )
    _write(
        repo_root,
        "specs/components/foo/requirements/R-FOO-001.md",
        ["# R-FOO-001", "", "foo MUST work."],
    )
    _write(
        repo_root,
        "specs/components/foo/requirements/R-FOO-002.md",
        ["# R-FOO-002", "", "foo MUST stop."],
    )
    _write(
        repo_root,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        ["# AC-FOO-001", "", "Covers: R-FOO-001", "Kind: generated-test"],
    )
    _write(
        repo_root,
        "specs/components/foo/interface/guarantees/G-FOO-001.md",
        ["# G-FOO-001", "", "foo never fails."],
    )
    _write(
        repo_root,
        "specs/product/x.md",
        [
            "---",
            "id: P-X",
            "title: X",
            "status: draft",
            "owners: [team]",
            "---",
            "",
            "# X",
            "",
            "### CS-X-001",
            "Covers: P-X",
            "",
            "### CS-X-002",
            "Covers: P-X",
        ],
    )
    _write(
        repo_root,
        "specs/vars/x.md",
        [
            "---",
            "id: VAR-X",
            "title: V",
            "status: draft",
            "owners: [team]",
            "---",
            "",
            "# V",
        ],
    )
    _write(
        repo_root,
        "specs/decisions/D1.md",
        [
            "---",
            "id: D1",
            "title: One",
            "status: ratified",
            "owners: [team]",
            "last_ratified_commit: 0000000",
            "---",
            "",
            "# D1",
        ],
    )
    _write(
        repo_root,
        "specs/decisions/D2.md",
        [
            "---",
            "id: D2",
            "title: Two",
            "status: draft",
            "owners: [team]",
            "supersedes: D1",
            "builds_on: [D1]",
            "---",
            "",
            "# D2",
        ],
    )
    for d in ("specs/product", "specs/vars", "specs/decisions"):
        _write(repo_root, d + "/README.md", ["# Readme", "", "Notes."])


def _snapshot(con):
    """Capture each view's columns and rows (order-insensitive), or the
    error class if querying it raises."""
    snap = {}
    for view in VIEWS:
        try:
            cur = con.execute("SELECT * FROM " + view)
            columns = [d[0] for d in cur.description]
            rows = cur.fetchall()
            snap[view] = ("ok", columns, sorted(repr(r) for r in rows))
        except Exception as exc:  # recorded and compared, not swallowed
            snap[view] = ("error", type(exc).__name__, None)
    return snap


def _kind_counts(con):
    rows = con.execute(
        "SELECT kind, count(*) FROM nodes GROUP BY kind"
    ).fetchall()
    return {k: c for k, c in rows}


def _edge_counts(con):
    rows = con.execute(
        "SELECT edge_type, count(*) FROM edges GROUP BY edge_type"
    ).fetchall()
    return {k: c for k, c in rows}


def test_ac_gqe_007_load_views_idempotent(tmp_path):
    repo_root = tmp_path.resolve()
    _build_fixture(repo_root)

    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")

    # Given: load_views already called once
    graph_query_engine.load_views(con, repo_root)
    first = _snapshot(con)
    first_kinds = _kind_counts(con)
    first_edges = _edge_counts(con)

    # The views every consumer relies on must actually be queryable.
    for view in ("nodes", "edges", "component_docs", "component_size",
                 "bundle_size", "decision_lineage", "component_context"):
        assert first[view][0] == "ok", (
            "view " + repr(view) + " not queryable after first load_views: "
            + repr(first[view])
        )

    # When: load_views is called again on the same connection
    # Then: it succeeds without error
    graph_query_engine.load_views(con, repo_root)

    # And every view still returns the same results as the first call
    second = _snapshot(con)
    for view in VIEWS:
        assert view in second
        assert second[view] == first[view], (
            "view " + repr(view) + " changed after second load_views: "
            + repr(first[view]) + " vs " + repr(second[view])
        )

    assert _kind_counts(con) == first_kinds
    assert _edge_counts(con) == first_edges

    # Sanity: results still match the fixture's documented shape.
    assert first_kinds == {
        "component": 2,
        "capability": 1,
        "var": 1,
        "decision": 2,
        "guarantee": 1,
        "requirement": 2,
        "acceptance": 1,
        "capability_scenario": 2,
    }
    assert first_edges == {
        "depends_on": 1,
        "realizes": 2,
        "uses_var": 1,
        "depends_on_guarantees": 1,
        "covers": 3,
        "supersedes": 1,
        "builds_on": 1,
    }

    # A third call is equally fine.
    graph_query_engine.load_views(con, repo_root)
    assert _snapshot(con) == first

    con.close()