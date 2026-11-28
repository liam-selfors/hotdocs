# hotdocs-criterion: sha256:5254322c01d5328c649c757d15d1477f03c47cd64e5be462739956f43c2827a1
"""AC-GQE-011: bundle_size view over the graph-query-engine fixture corpus (R-GQE-009)."""

from pathlib import Path

import duckdb

import graph_query_engine


def _write(repo_root, rel, lines):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _foo_component_lines():
    return [
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
    ]


def _bar_component_lines():
    return [
        "---",
        "id: comp-bar",
        "title: Bar",
        "status: draft",
        "owners: [team]",
        "realizes: [P-X]",
        "---",
        "",
        "# Bar",
    ]


def _write_fixture(repo_root, foo_extra=None, bar_extra=None):
    _write(
        repo_root,
        "specs/components/foo/component.md",
        _foo_component_lines() + list(foo_extra or []),
    )
    _write(
        repo_root,
        "specs/components/bar/component.md",
        _bar_component_lines() + list(bar_extra or []),
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


def _bundle_sizes(repo_root):
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, Path(repo_root))
        rows = con.execute(
            "SELECT component_id, generator_words, criterion_words_max FROM bundle_size"
        ).fetchall()
    finally:
        con.close()
    result = {}
    for component_id, generator_words, criterion_words_max in rows:
        assert component_id not in result, "duplicate row for " + repr(component_id)
        result[component_id] = (generator_words, criterion_words_max)
    return result


def test_bundle_size_on_base_fixture(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    sizes = _bundle_sizes(repo_root)

    assert set(sizes) == {"foo", "bar"}
    assert sizes["foo"][0] == 20
    assert sizes["foo"][1] == 16
    assert sizes["bar"][0] == 2
    assert sizes["bar"][1] == 0


def test_bundle_size_drops_excluded_sections_and_counts_dependency_purpose(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(
        repo_root,
        foo_extra=["", "## Rationale", "", "Old reasons here."],
        bar_extra=[
            "",
            "## Purpose",
            "",
            "Bar holds data.",
            "",
            "## Change log",
            "",
            "- D1 added it.",
        ],
    )

    sizes = _bundle_sizes(repo_root)

    assert set(sizes) == {"foo", "bar"}
    assert sizes["foo"][0] == 24
    assert sizes["bar"][0] == 6