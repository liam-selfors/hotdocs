# hotdocs-criterion: sha256:ada076acbf2f325e20d7526d71081e5c0f83fe3a5902a623677a2f3e388b28c7
from pathlib import Path

import duckdb

import graph_query_engine


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _fm(lines):
    return "---\n" + "\n".join(lines) + "\n---\n"


def _build_fixture(repo_root):
    specs = repo_root / "specs"

    _write(
        specs / "components" / "foo" / "component.md",
        _fm(
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
        _fm(
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
        specs / "components" / "foo" / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: generated-test\n",
    )
    _write(
        specs / "components" / "foo" / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n\nfoo never fails.\n",
    )
    _write(
        specs / "product" / "x.md",
        _fm(["id: P-X", "title: X", "status: draft", "owners: [team]"])
        + "# X\n\n### CS-X-001\nCovers: P-X\n\n### CS-X-002\nCovers: P-X\n",
    )
    _write(
        specs / "vars" / "x.md",
        _fm(["id: VAR-X", "title: V", "status: draft", "owners: [team]"])
        + "# V\n",
    )
    # Decision with last_ratified_commit set.
    _write(
        specs / "decisions" / "D1.md",
        _fm(
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
    # Decision with no last_ratified_commit field at all.
    _write(
        specs / "decisions" / "D2.md",
        _fm(
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
    for d in ("product", "vars", "decisions"):
        _write(specs / d / "README.md", "# Readme\n\nNotes.\n")


def test_ac_gqe_008_decision_lineage(tmp_path):
    repo_root = Path(tmp_path) / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, repo_root)

        cur = con.execute("SELECT * FROM decision_lineage")
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()

        assert sorted(columns) == ["id", "last_ratified_commit"]

        id_idx = columns.index("id")
        commit_idx = columns.index("last_ratified_commit")
        by_id = {}
        for row in rows:
            by_id[row[id_idx]] = row[commit_idx]

        assert sorted(by_id.keys()) == ["D1", "D2"]
        assert len(rows) == 2

        assert by_id["D1"] == "0000000"

        assert by_id["D2"] is None
        assert by_id["D2"] != ""

        null_count = con.execute(
            "SELECT count(*) FROM decision_lineage "
            "WHERE id = 'D2' AND last_ratified_commit IS NULL"
        ).fetchone()[0]
        assert null_count == 1
    finally:
        con.close()