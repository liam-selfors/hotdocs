# hotdocs-criterion: sha256:91c37f9a948839a8290d97729be6f8232e04623324eeb971f343c8f951681894
"""AC-GQE-002: edges view row counts per edge_type over the fixture corpus."""

from pathlib import Path

import duckdb

import graph_query_engine


def _write(repo_root, rel, text):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _build_fixture(repo_root):
    _write(
        repo_root,
        "specs/components/foo/component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: [comp-bar]\n"
        "realizes: [P-X]\n"
        "uses_var: [VAR-X]\n"
        "depends_on_guarantees: [G-BAR-001]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "one two three\n",
    )
    _write(
        repo_root,
        "specs/components/bar/component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-X]\n"
        "---\n"
        "\n"
        "# Bar\n",
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
        "id: P-X\n"
        "title: X\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "# X\n"
        "\n"
        "### CS-X-001\n"
        "Covers: P-X\n"
        "\n"
        "### CS-X-002\n"
        "Covers: P-X\n",
    )
    _write(
        repo_root,
        "specs/vars/x.md",
        "---\n"
        "id: VAR-X\n"
        "title: V\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "# V\n",
    )
    _write(
        repo_root,
        "specs/decisions/D1.md",
        "---\n"
        "id: D1\n"
        "title: One\n"
        "status: ratified\n"
        "owners: [team]\n"
        "last_ratified_commit: 0000000\n"
        "---\n"
        "# D1\n",
    )
    _write(
        repo_root,
        "specs/decisions/D2.md",
        "---\n"
        "id: D2\n"
        "title: Two\n"
        "status: draft\n"
        "owners: [team]\n"
        "supersedes: D1\n"
        "builds_on: [D1]\n"
        "---\n"
        "# D2\n",
    )
    for d in ("specs/product", "specs/vars", "specs/decisions"):
        _write(repo_root, d + "/README.md", "# Readme\n\nNotes.\n")


def test_ac_gqe_002_edges_counts_per_edge_type(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, repo_root)

        rows = con.execute(
            "SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type"
        ).fetchall()
    finally:
        con.close()

    counts = {r[0]: r[1] for r in rows}
    expected = {
        "depends_on": 1,
        "realizes": 2,
        "uses_var": 1,
        "depends_on_guarantees": 1,
        "covers": 3,
        "supersedes": 1,
        "builds_on": 1,
    }
    assert counts == expected