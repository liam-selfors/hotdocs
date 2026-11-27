# hotdocs-criterion: sha256:1ec2be7a3a497a2163e46969a6388106d64ca81dd3f80e41f27b546d5520bbaa
"""AC-GQE-006: component_size returns foo 26 and bar 2 for the fixture corpus."""

from pathlib import Path

import duckdb

import graph_query_engine


FIXTURE_FILES = {
    "specs/components/foo/component.md": (
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
        "one two three\n"
    ),
    "specs/components/bar/component.md": (
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-X]\n"
        "---\n"
        "\n"
        "# Bar\n"
    ),
    "specs/components/foo/requirements/R-FOO-001.md": (
        "# R-FOO-001\n"
        "\n"
        "foo MUST work.\n"
    ),
    "specs/components/foo/requirements/R-FOO-002.md": (
        "# R-FOO-002\n"
        "\n"
        "foo MUST stop.\n"
    ),
    "specs/components/foo/acceptance/AC-FOO-001.md": (
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
    ),
    "specs/components/foo/interface/guarantees/G-FOO-001.md": (
        "# G-FOO-001\n"
        "\n"
        "foo never fails.\n"
    ),
    "specs/product/x.md": (
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
        "Covers: P-X\n"
    ),
    "specs/vars/x.md": (
        "---\n"
        "id: VAR-X\n"
        "title: V\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "# V\n"
    ),
    "specs/decisions/D1.md": (
        "---\n"
        "id: D1\n"
        "title: One\n"
        "status: ratified\n"
        "owners: [team]\n"
        "last_ratified_commit: 0000000\n"
        "---\n"
        "# D1\n"
    ),
    "specs/decisions/D2.md": (
        "---\n"
        "id: D2\n"
        "title: Two\n"
        "status: draft\n"
        "owners: [team]\n"
        "supersedes: D1\n"
        "builds_on: [D1]\n"
        "---\n"
        "# D2\n"
    ),
    "specs/product/README.md": "# Readme\n\nNotes.\n",
    "specs/vars/README.md": "# Readme\n\nNotes.\n",
    "specs/decisions/README.md": "# Readme\n\nNotes.\n",
}


def write_fixture(repo_root: Path) -> None:
    for rel, text in FIXTURE_FILES.items():
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))


def test_ac_gqe_006_component_size_word_counts(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_fixture(repo_root)

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

    result = {component_id: word_count for component_id, word_count in rows}

    # One row per component, keyed by bare component name.
    assert len(rows) == 2, rows
    assert set(result) == {"foo", "bar"}, result
    assert result["foo"] == 26, result
    assert result["bar"] == 2, result