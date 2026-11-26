# hotdocs-criterion: sha256:d78780b2bbc092ce471c3b773366a144e0bc5dbaecafc1863e8937f7954f018b
from pathlib import Path

import duckdb

import graph_query_engine


PURPOSE_LINES = [
    "Baz keeps the first line of its purpose here.",
    "It continues the purpose on a second line.",
    "And finishes it on a third line.",
]


def write(repo_root, rel, text):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def build_fixture(repo_root):
    write(
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
    write(
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
    write(
        repo_root,
        "specs/components/baz/component.md",
        "---\n"
        "id: comp-baz\n"
        "title: Baz\n"
        "status: draft\n"
        "owners: [team]\n"
        "sealed: true\n"
        "source_path: legacy/baz/\n"
        "---\n"
        "\n"
        "# Baz\n"
        "\n"
        "## Purpose\n"
        "\n"
        + "\n".join(PURPOSE_LINES)
        + "\n"
        "\n"
        "## Rules\n"
        "\n"
        "Baz MUST behave.\n",
    )
    write(
        repo_root,
        "specs/components/foo/requirements/R-FOO-001.md",
        "# R-FOO-001\n\nfoo MUST work.\n",
    )
    write(
        repo_root,
        "specs/components/foo/requirements/R-FOO-002.md",
        "# R-FOO-002\n\nfoo MUST stop.\n",
    )
    write(
        repo_root,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )
    write(
        repo_root,
        "specs/components/foo/acceptance/AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: generated-test\n",
    )
    write(
        repo_root,
        "specs/components/foo/interface/guarantees/G-FOO-001.md",
        "# G-FOO-001\n\nfoo never fails.\n",
    )
    write(
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
    write(
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
    write(
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
    write(
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
        write(repo_root, d + "/README.md", "# Readme\n\nNotes.\n")


def test_ac_gqe_004_component_context_multiline_purpose(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, repo_root)

        rows = con.execute(
            "SELECT purpose FROM component_context WHERE component_id = ?",
            ["comp-baz"],
        ).fetchall()
    finally:
        con.close()

    assert len(rows) == 1, rows
    purpose = rows[0][0]
    assert purpose is not None
    assert purpose != ""
    assert purpose.strip() != ""
    for line in PURPOSE_LINES:
        assert line in purpose, (line, purpose)
    assert purpose.strip() == "\n".join(PURPOSE_LINES)
    assert "\n" in purpose.strip()
    assert "## Rules" not in purpose
    assert "Baz MUST behave." not in purpose