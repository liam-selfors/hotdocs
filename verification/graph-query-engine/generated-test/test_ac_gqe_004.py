# hotdocs-criterion: sha256:ffd473232d0c841f5205e0e31b5a9e7047af10801e778ee9b22b2518d19db4e9
"""AC-GQE-004: component_context extracts a multi-line Purpose section in full.

Given a component whose Purpose section spans multiple lines
When load_views runs and component_context is queried for it
Then purpose contains the full multi-line text, not an empty string
"""

from pathlib import Path

import duckdb

import graph_query_engine


PURPOSE_LINES = [
    "Line one of the ctx purpose.",
    "Line two of the ctx purpose.",
    "Line three of the ctx purpose.",
]


def _write(repo_root, rel, text):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


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
        "\n"
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
        "\n"
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
        "\n"
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
        "\n"
        "# D2\n",
    )
    for d in ("specs/product", "specs/vars", "specs/decisions"):
        _write(repo_root, d + "/README.md", "# Readme\n\nNotes.\n")

    # The component under test for this criterion: a multi-line Purpose
    # section, followed by another "##" section.
    _write(
        repo_root,
        "specs/components/ctx/component.md",
        "---\n"
        "id: comp-ctx\n"
        "title: Ctx\n"
        "status: draft\n"
        "owners: [team]\n"
        "sealed: true\n"
        "source_path: legacy/ctx/\n"
        "---\n"
        "\n"
        "# Ctx\n"
        "\n"
        "## Purpose\n"
        "\n"
        + "\n".join(PURPOSE_LINES)
        + "\n"
        "\n"
        "## Rules\n"
        "\n"
        "Some rules text.\n",
    )


def _connect():
    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    return con


def test_component_context_multiline_purpose(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    con = _connect()
    try:
        graph_query_engine.load_views(con, repo_root)
        rows = con.execute(
            "SELECT component_id, purpose FROM component_context "
            "WHERE component_id = 'comp-ctx'"
        ).fetchall()
    finally:
        con.close()

    assert len(rows) == 1, rows
    component_id, purpose = rows[0]
    assert component_id == "comp-ctx"

    assert purpose is not None
    assert purpose != ""
    assert purpose.strip() != ""

    # The full multi-line text, every line present, in order.
    for line in PURPOSE_LINES:
        assert line in purpose, (line, purpose)
    assert "\n" in purpose.strip()
    assert purpose.strip() == "\n".join(PURPOSE_LINES)

    # Nothing from the following section leaks in.
    assert "## Rules" not in purpose
    assert "Some rules text." not in purpose