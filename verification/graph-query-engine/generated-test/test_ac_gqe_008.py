"""AC-GQE-008: decision_lineage returns id + last_ratified_commit only,
with NULL (not empty string) when the field is absent."""

import json
from pathlib import Path

import duckdb
import pytest

import graph_query_engine


RATIFIED_COMMIT = "0123456789abcdef0123456789abcdef01234567"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root: Path, slug: str, depends_on: str) -> None:
    upper = slug.upper()
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} Component\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        f"depends_on: {depends_on}\n"
        "realizes: []\n"
        "uses_var: [VAR-FOO]\n"
        "depends_on_guarantees: []\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        "\n"
        f"# {slug.capitalize()} Component\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Does a small {slug} thing for the fixture corpus.\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n",
    )
    _write(
        base / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — The component MUST do the {slug} thing.\n",
    )
    _write(
        base / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )
    _write(
        base / "interface" / "library.md",
        f"# Library\n\n```\ndo_{slug}() -> None\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        repo_root / "gen" / slug / ".provenance.json",
        json.dumps(
            {
                "component_id": f"comp-{slug}",
                "spec_bundle_hash": "deadbeef" * 8,
                "verification_report": {"status": "pass"},
                "license_scan": {"status": "pass"},
                "secret_scan": {"status": "pass"},
                "provenance_hit": False,
            }
        ),
    )


def _build_repo(repo_root: Path) -> None:
    _component(repo_root, "foo", "[]")
    _component(repo_root, "bar", "[comp-foo]")

    _write(
        repo_root / "specs" / "vars" / "VAR-FOO.md",
        "---\n"
        "id: VAR-FOO\n"
        "title: Foo Var\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# VAR-FOO\n\nA fixture variable.\n",
    )
    _write(
        repo_root / "specs" / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo Capability\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# P-FOO\n\nA fixture capability.\n",
    )

    # Decision WITH last_ratified_commit.
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: First Decision\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        f"last_ratified_commit: {RATIFIED_COMMIT}\n"
        "supersedes: []\n"
        "builds_on: []\n"
        "---\n"
        "\n"
        "# D1\n\nA ratified decision.\n",
    )
    # Decision with NO last_ratified_commit field at all.
    _write(
        repo_root / "specs" / "decisions" / "D2.md",
        "---\n"
        "id: D2\n"
        "title: Second Decision\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "supersedes: []\n"
        "builds_on: [D1]\n"
        "---\n"
        "\n"
        "# D2\n\nA draft decision, never ratified.\n",
    )


@pytest.fixture
def con():
    connection = duckdb.connect()
    connection.execute("INSTALL yaml FROM community")
    connection.execute("LOAD yaml")
    try:
        yield connection
    finally:
        connection.close()


def test_decision_lineage_null_for_missing_commit_and_only_two_columns(tmp_path, con):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)

    graph_query_engine.load_views(con, repo_root)

    cursor = con.execute(
        "SELECT * FROM decision_lineage ORDER BY id"
    )
    columns = [d[0] for d in cursor.description]
    rows = cursor.fetchall()

    # The view has no other columns than id and last_ratified_commit.
    assert sorted(columns) == ["id", "last_ratified_commit"]
    assert len(columns) == 2

    by_id = {
        row[columns.index("id")]: row[columns.index("last_ratified_commit")]
        for row in rows
    }
    assert set(by_id) == {"D1", "D2"}
    assert len(rows) == 2

    # First row: the ratified commit.
    assert by_id["D1"] == RATIFIED_COMMIT

    # Second row: SQL NULL, not an empty string.
    assert by_id["D2"] is None
    assert by_id["D2"] != ""

    null_check = con.execute(
        "SELECT last_ratified_commit IS NULL FROM decision_lineage WHERE id = 'D2'"
    ).fetchall()
    assert null_check == [(True,)]