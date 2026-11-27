# hotdocs-criterion: sha256:ff9a203f7d53e9ea2bb0e78afa23b385afb14294cd17b144669c0999c34fe88d
"""AC-GQE-001: nodes view row counts per kind over the fixture corpus.

Fixture: specs/architecture/graph-query-engine-fixture.md, written under a
temporary repo_root, README.md files included.
"""

from pathlib import Path

import duckdb

import graph_query_engine


def _write(repo_root, rel, lines):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    path.write_bytes(text.encode("utf-8"))


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


def test_ac_gqe_001_nodes_row_count_per_kind(tmp_path):
    repo_root = tmp_path.resolve()
    _build_fixture(repo_root)

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, repo_root)

        rows = con.execute(
            "SELECT kind, count(*) FROM nodes GROUP BY kind"
        ).fetchall()
        counts = {kind: int(n) for kind, n in rows}

        expected = {
            "component": 2,
            "capability": 1,
            "var": 1,
            "decision": 2,
            "guarantee": 1,
            "requirement": 2,
            "acceptance": 1,
            "capability_scenario": 2,
        }
        assert counts == expected

        null_ids = con.execute(
            "SELECT count(*) FROM nodes WHERE id IS NULL"
        ).fetchone()[0]
        assert int(null_ids) == 0
    finally:
        con.close()