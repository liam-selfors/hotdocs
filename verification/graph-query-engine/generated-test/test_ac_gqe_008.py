# hotdocs-criterion: sha256:f4a0b7e03c15169051301511f36cea6ef7c8fd16d1862608e226d9bfe12a6df8
import duckdb

import graph_query_engine


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _frontmatter(lines):
    return "---\n" + "\n".join(lines) + "\n---\n"


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
        + "\n# Foo\n\none two three\n",
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
        _frontmatter(["id: P-X", "title: X", "status: draft", "owners: [team]"])
        + "# X\n\n### CS-X-001\nCovers: P-X\n\n### CS-X-002\nCovers: P-X\n",
    )
    _write(
        specs / "vars" / "x.md",
        _frontmatter(["id: VAR-X", "title: V", "status: draft", "owners: [team]"])
        + "# V\n",
    )

    # Decision with last_ratified_commit set.
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
        + "# D1\n",
    )
    # Decision with no last_ratified_commit field at all.
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
        + "# D2\n",
    )

    for sub in ("product", "vars", "decisions"):
        _write(specs / sub / "README.md", "# Readme\n\nNotes.\n")


def test_ac_gqe_008_decision_lineage_columns_and_null_commit(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")

        graph_query_engine.load_views(con, repo_root)

        cur = con.execute("SELECT * FROM decision_lineage ORDER BY id")
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
    finally:
        con.close()

    # The view has no columns other than id and last_ratified_commit.
    assert sorted(columns) == ["id", "last_ratified_commit"]
    assert len(columns) == 2

    by_id = {}
    for row in rows:
        record = dict(zip(columns, row))
        by_id[record["id"]] = record

    # One row per decision record; the frontmatter-less README is not a row.
    assert len(rows) == 2
    assert set(by_id) == {"D1", "D2"}

    # The ratified decision carries its commit.
    assert by_id["D1"]["last_ratified_commit"] == "0000000"

    # The decision with no field at all yields NULL, not an empty string.
    assert by_id["D2"]["last_ratified_commit"] is None
    assert by_id["D2"]["last_ratified_commit"] != ""