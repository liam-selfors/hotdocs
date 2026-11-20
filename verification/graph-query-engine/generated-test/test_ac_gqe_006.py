# hotdocs-criterion: sha256:e3dbd054160223f26c6afbeb1de084041ca4b5b176a29d47639ea890bf05d5dd
"""AC-GQE-006: component_size returns foo's word_count 26 and bar's 2 for the fixture corpus."""

from pathlib import Path

import duckdb

import graph_query_engine


def _write(repo_root: Path, rel: str, lines):
    path = repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    path.write_bytes(text.encode("utf-8"))


def _build_fixture(repo_root: Path) -> None:
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
            "# X",
            "### CS-X-001",
            "Covers: P-X",
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
            "# D2",
        ],
    )
    for d in ("specs/product", "specs/vars", "specs/decisions"):
        _write(repo_root, d + "/README.md", ["# Readme", "", "Notes."])


def test_ac_gqe_006_component_size_word_counts(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, repo_root)

        rows = con.execute(
            "SELECT component_id, word_count FROM component_size"
        ).fetchall()
    finally:
        con.close()

    sizes = {}
    for component_id, word_count in rows:
        assert component_id not in sizes, "duplicate row for " + repr(component_id)
        sizes[component_id] = word_count

    assert "foo" in sizes, "no component_size row for foo: " + repr(rows)
    assert "bar" in sizes, "no component_size row for bar: " + repr(rows)
    assert int(sizes["foo"]) == 26, "foo word_count: " + repr(sizes["foo"])
    assert int(sizes["bar"]) == 2, "bar word_count: " + repr(sizes["bar"])