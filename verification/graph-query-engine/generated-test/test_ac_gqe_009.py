# hotdocs-criterion: sha256:fadcf12b6dceedc72c382783bc3c72aa81c46e9038595d07e79f0f8a3946bb86
"""AC-GQE-009: a scalar `supersedes: D2` line yields exactly one supersedes edge,
and both decisions (one deprecated) appear as `decision` nodes."""

from pathlib import Path

import duckdb

import graph_query_engine


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _build_fixture(repo_root):
    specs = repo_root / "specs"

    # One component (sealed, no realizes needed).
    _write(
        specs / "components" / "foo" / "component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "one two three\n",
    )
    # Unit files (no frontmatter); each requirement has a covering acceptance file.
    _write(
        specs / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n" + "\n" + "foo MUST work.\n",
    )
    _write(
        specs / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n" + "\n" + "Covers: R-FOO-001\n" + "Kind: generated-test\n",
    )
    _write(
        specs / "components" / "foo" / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n" + "\n" + "foo never fails.\n",
    )

    # Product and vars directories, so every glob in the views resolves.
    _write(
        specs / "product" / "x.md",
        "---\n"
        + "id: P-X\n"
        + "title: X\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "\n"
        + "# X\n",
    )
    _write(
        specs / "vars" / "x.md",
        "---\n"
        + "id: VAR-X\n"
        + "title: V\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "\n"
        + "# V\n",
    )

    # Two decisions: D1 has a scalar supersedes line; D2 is deprecated.
    _write(
        specs / "decisions" / "D1.md",
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
        specs / "decisions" / "D2.md",
        "---\n"
        + "id: D2\n"
        + "title: Two\n"
        + "status: deprecated\n"
        + "owners: [team]\n"
        + "last_ratified_commit: 0000000\n"
        + "---\n"
        + "\n"
        + "# D2\n",
    )

    for sub in ("product", "vars", "decisions"):
        _write(specs / sub / "README.md", "# Readme\n" + "\n" + "Notes.\n")


def test_ac_gqe_009_scalar_supersedes_yields_single_edge(tmp_path):
    repo_root = Path(tmp_path).resolve()
    _build_fixture(repo_root)

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, repo_root)

        decision_rows = con.execute(
            "SELECT id, kind FROM nodes WHERE id IN ('D1', 'D2') ORDER BY id"
        ).fetchall()
        assert [(str(r[0]), str(r[1])) for r in decision_rows] == [
            ("D1", "decision"),
            ("D2", "decision"),
        ]

        decision_kind_ids = sorted(
            str(r[0])
            for r in con.execute(
                "SELECT id FROM nodes WHERE kind = 'decision'"
            ).fetchall()
        )
        assert decision_kind_ids == ["D1", "D2"]

        decision_edges = con.execute(
            "SELECT source_id, target_id, edge_type FROM edges "
            "WHERE source_id IN ('D1', 'D2') "
            "OR target_id IN ('D1', 'D2') "
            "OR edge_type IN ('supersedes', 'builds_on')"
        ).fetchall()
        assert [tuple(str(v) for v in r) for r in decision_edges] == [
            ("D1", "D2", "supersedes")
        ]
    finally:
        con.close()