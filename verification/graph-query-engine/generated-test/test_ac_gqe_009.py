# hotdocs-criterion: sha256:f4d4aec4f5dcc10b5c3ff9425c9f0ca402a0fc4850969c6682afe8dca527b85c
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
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "---\n"
        + "\n"
        + "# Foo\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        + "id: D1\n"
        + "title: One\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "supersedes: D2\n"
        + "---\n"
        + "\n"
        + "# D1\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D2.md",
        "---\n"
        + "id: D2\n"
        + "title: Two\n"
        + "status: deprecated\n"
        + "owners: [team]\n"
        + "---\n"
        + "\n"
        + "# D2\n",
    )


def _connect():
    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    return con


def test_ac_gqe_009_scalar_supersedes_yields_one_edge(tmp_path):
    repo_root = Path(tmp_path).resolve()
    _build_fixture(repo_root)

    con = _connect()
    try:
        graph_query_engine.load_views(con, repo_root)

        node_rows = con.execute(
            "SELECT id, kind FROM nodes WHERE id IN ('D1', 'D2') ORDER BY id"
        ).fetchall()
        assert node_rows == [("D1", "decision"), ("D2", "decision")], node_rows

        decision_ids = sorted(
            r[0]
            for r in con.execute(
                "SELECT id FROM nodes WHERE kind = 'decision'"
            ).fetchall()
        )
        assert decision_ids == ["D1", "D2"], decision_ids

        edge_rows = con.execute(
            "SELECT source_id, target_id, edge_type FROM edges"
        ).fetchall()
        assert sorted(edge_rows) == [("D1", "D2", "supersedes")], edge_rows
    finally:
        con.close()