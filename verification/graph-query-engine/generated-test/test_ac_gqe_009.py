# hotdocs-criterion: sha256:c9fceac75f277af820af44af515049c5c231c1a40df2e34eb0d8ebf5bd5c0382
"""AC-GQE-009: a decision's scalar `supersedes:` frontmatter line yields
exactly one `supersedes` edge, and both decisions appear in `nodes` with
kind "decision" (R-GQE-001)."""

from pathlib import Path

import duckdb

import graph_query_engine


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _build_fixture(repo_root):
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "one two three\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: One\n"
        "status: draft\n"
        "owners: [team]\n"
        "supersedes: D2\n"
        "---\n"
        "\n"
        "# D1\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D2.md",
        "---\n"
        "id: D2\n"
        "title: Two\n"
        "status: deprecated\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# D2\n",
    )


def _connect():
    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    return con


def test_ac_gqe_009_scalar_supersedes_edge_and_decision_nodes(tmp_path):
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _build_fixture(repo_root)

    con = _connect()
    try:
        graph_query_engine.load_views(con, repo_root)

        decision_rows = con.execute(
            "SELECT id, kind FROM nodes WHERE id IN ('D1', 'D2') ORDER BY id"
        ).fetchall()
        assert [(str(r[0]), str(r[1])) for r in decision_rows] == [
            ("D1", "decision"),
            ("D2", "decision"),
        ]

        kind_decision_ids = sorted(
            str(r[0])
            for r in con.execute(
                "SELECT id FROM nodes WHERE kind = 'decision'"
            ).fetchall()
        )
        assert kind_decision_ids == ["D1", "D2"]

        edge_rows = con.execute(
            "SELECT source_id, target_id, edge_type FROM edges"
        ).fetchall()
        edges = [(str(r[0]), str(r[1]), str(r[2])) for r in edge_rows]
        assert edges == [("D1", "D2", "supersedes")]
    finally:
        con.close()