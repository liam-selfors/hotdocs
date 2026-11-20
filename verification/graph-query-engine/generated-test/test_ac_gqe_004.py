# hotdocs-criterion: sha256:bca7d68242793d141ad15d3e7b78251185bd96d632f91795a01478c5b2dd309b
import duckdb

import graph_query_engine


PURPOSE_LINES = [
    "Foo keeps the first line of its purpose here.",
    "It continues the same purpose on a second line.",
    "And finishes it on a third line.",
]

BAR_PURPOSE_LINES = [
    "Bar has a purpose too.",
    "It also spans two lines.",
]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _build_corpus(repo_root):
    specs = repo_root / "specs"

    foo_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: [comp-bar]\n"
        "realizes: [P-X]\n"
        "uses_var: [VAR-X]\n"
        "depends_on_guarantees: [G-BAR-001]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        + "\n".join(PURPOSE_LINES)
        + "\n"
        "\n"
        "## Notes\n"
        "\n"
        "one two three\n"
    )
    _write(specs / "components" / "foo" / "component.md", foo_md)

    bar_md = (
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [team]\n"
        "sealed: true\n"
        "source_path: legacy/bar/\n"
        "realizes: [P-X]\n"
        "---\n"
        "\n"
        "# Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        + "\n".join(BAR_PURPOSE_LINES)
        + "\n"
        "\n"
        "## Notes\n"
        "\n"
        "Nothing else.\n"
    )
    _write(specs / "components" / "bar" / "component.md", bar_md)

    foo = specs / "components" / "foo"
    _write(foo / "requirements" / "R-FOO-001.md", "# R-FOO-001\n\nfoo MUST work.\n")
    _write(foo / "requirements" / "R-FOO-002.md", "# R-FOO-002\n\nfoo MUST stop.\n")
    _write(
        foo / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )
    _write(
        foo / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: generated-test\n",
    )
    _write(
        foo / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n\nfoo never fails.\n",
    )

    _write(
        specs / "product" / "x.md",
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
        specs / "vars" / "x.md",
        "---\n"
        "id: VAR-X\n"
        "title: V\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "# V\n",
    )
    _write(
        specs / "decisions" / "D1.md",
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
        specs / "decisions" / "D2.md",
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
    for sub in ("product", "vars", "decisions"):
        _write(specs / sub / "README.md", "# Readme\n\nNotes.\n")


def _load(repo_root):
    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    graph_query_engine.load_views(con, repo_root)
    return con


def _purposes(con):
    rows = con.execute(
        "SELECT component_id, purpose FROM component_context"
    ).fetchall()
    return rows


def test_multiline_purpose_is_extracted_in_full(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    con = _load(repo_root)
    try:
        rows = _purposes(con)
    finally:
        con.close()

    foo_rows = [r for r in rows if r[0] == "comp-foo"]
    assert len(foo_rows) == 1, rows
    purpose = foo_rows[0][1]

    assert purpose is not None
    assert purpose != ""
    assert purpose.strip() != ""
    # Spans multiple lines: every line is present and newlines are kept.
    assert "\n" in purpose.strip()
    for line in PURPOSE_LINES:
        assert line in purpose, (line, purpose)
    assert purpose.strip() == "\n".join(PURPOSE_LINES)
    # Stops at the next section, does not swallow it.
    assert "## Notes" not in purpose
    assert "one two three" not in purpose


def test_every_component_with_multiline_purpose_gets_full_text(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    con = _load(repo_root)
    try:
        rows = _purposes(con)
    finally:
        con.close()

    by_id = {}
    for component_id, purpose in rows:
        assert component_id not in by_id, rows
        by_id[component_id] = purpose

    assert set(by_id) == {"comp-foo", "comp-bar"}, rows
    assert by_id["comp-bar"] is not None
    assert by_id["comp-bar"].strip() == "\n".join(BAR_PURPOSE_LINES)
    assert by_id["comp-foo"].strip() == "\n".join(PURPOSE_LINES)