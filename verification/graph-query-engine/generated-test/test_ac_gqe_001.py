# hotdocs-criterion: sha256:acde9090f85207a937285a91b9d628e921ed3786d092955aa2b1bd55a7fc3271
from pathlib import Path

import duckdb

import graph_query_engine


def _write(repo_root, rel, text):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _frontmatter(lines):
    return "---\n" + "\n".join(lines) + "\n---\n"


def _build_fixture(repo_root):
    _write(
        repo_root,
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
        + "\n# Foo\n\none two three\n",
    )
    _write(
        repo_root,
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
        + "\n# Bar\n",
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
        _frontmatter(
            [
                "id: P-X",
                "title: X",
                "status: draft",
                "owners: [team]",
            ]
        )
        + "\n# X\n\n### CS-X-001\nCovers: P-X\n\n### CS-X-002\nCovers: P-X\n",
    )
    _write(
        repo_root,
        "specs/vars/x.md",
        _frontmatter(
            [
                "id: VAR-X",
                "title: V",
                "status: draft",
                "owners: [team]",
            ]
        )
        + "\n# V\n",
    )
    _write(
        repo_root,
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
        + "\n# D1\n",
    )
    _write(
        repo_root,
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
        + "\n# D2\n",
    )
    for d in ("specs/product", "specs/vars", "specs/decisions"):
        _write(repo_root, d + "/README.md", "# Readme\n\nNotes.\n")


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
        counts = {kind: n for kind, n in rows}

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
        assert null_ids == 0
    finally:
        con.close()