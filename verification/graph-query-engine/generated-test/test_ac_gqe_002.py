# hotdocs-criterion: sha256:a8be757c0820b53d1cfbb835db28f29658a25416ff523dd2097a012935013420
"""AC-GQE-002: edges row count per edge_type over the fixture corpus."""

from pathlib import Path

import duckdb

import graph_query_engine


def _write(repo_root, rel, text):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _build_fixture(repo_root):
    _write(
        repo_root,
        "specs/components/foo/component.md",
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
        repo_root,
        "specs/components/bar/component.md",
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
        repo_root,
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
        repo_root,
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
        repo_root,
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
    for d in ("specs/product", "specs/vars", "specs/decisions"):
        _write(repo_root, d + "/README.md", "# Readme\n\nNotes.\n")


def test_ac_gqe_002_edges_row_count_per_edge_type(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, repo_root)

        rows = con.execute(
            "SELECT edge_type, count(*) FROM edges GROUP BY edge_type"
        ).fetchall()
    finally:
        con.close()

    counts = {edge_type: int(n) for edge_type, n in rows}
    assert counts == {
        "depends_on": 1,
        "realizes": 2,
        "uses_var": 1,
        "depends_on_guarantees": 1,
        "covers": 3,
        "supersedes": 1,
        "builds_on": 1,
    }