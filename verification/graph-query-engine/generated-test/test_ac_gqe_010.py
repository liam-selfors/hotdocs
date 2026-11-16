"""AC-GQE-010 (Covers: R-GQE-002).

The `edges` view's decision arms (`supersedes`/`builds_on`) read only a
decision record's frontmatter block, never its prose:

* a decision whose prose quotes `supersedes: D1` and `builds_on: [D2]` but
  whose frontmatter declares neither yields no supersedes/builds_on row;
* a decision whose frontmatter declares `builds_on: [D1, D2]` yields exactly
  the rows (that decision, D1, builds_on) and (that decision, D2, builds_on).
"""

import json
from pathlib import Path

import duckdb
import pytest

import graph_query_engine


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def _build_repo(repo_root: Path) -> None:
    """A small but complete synthetic spec corpus, so that every view's glob
    matches at least one file and every frontmatter column is present."""
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: [VAR-FOO]\n"
        "depends_on_guarantees: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Does foo things for the fixture corpus.\n"
        "\n"
        "## Scope\n"
        "\n"
        "Nothing else.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — The component MUST do foo.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: judged\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When foo runs\n"
        "Then foo happens\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nfoo() -> None\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    _write(
        repo_root / "specs" / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Foo capability\n"
        "\n"
        "## Scenarios\n"
        "\n"
        "### CS-FOO-001\n"
        "Covers: P-FOO\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "Then foo\n"
        "```\n",
    )

    _write(
        repo_root / "specs" / "vars" / "VAR-FOO.md",
        "---\n"
        "id: VAR-FOO\n"
        "title: Foo var\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# VAR-FOO\n\nA foo variable.\n",
    )

    decisions = repo_root / "specs" / "decisions"
    _write(
        decisions / "D1.md",
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: ratified\n"
        "owners: [pipeline-team]\n"
        "last_ratified_commit: abc1234\n"
        "---\n"
        "\n"
        "# D1\n\nThe first decision.\n",
    )
    _write(
        decisions / "D2.md",
        "---\n"
        "id: D2\n"
        "title: Second decision\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# D2\n\nThe second decision.\n",
    )
    # D3: prose quotes both fields (inline and at a line start inside a code
    # block), frontmatter declares neither.
    _write(
        decisions / "D3.md",
        "---\n"
        "id: D3\n"
        "title: Third decision quoting fields\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# D3\n"
        "\n"
        "An earlier draft of this record declared `supersedes: D1` and\n"
        "`builds_on: [D2]`; neither applies, and neither is declared.\n"
        "\n"
        "```yaml\n"
        "supersedes: D1\n"
        "builds_on: [D2]\n"
        "```\n",
    )
    # D4: frontmatter declares builds_on: [D1, D2].
    _write(
        decisions / "D4.md",
        "---\n"
        "id: D4\n"
        "title: Fourth decision\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "builds_on: [D1, D2]\n"
        "---\n"
        "\n"
        "# D4\n\nBuilds on the first two decisions.\n",
    )

    manifest = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "0" * 64,
        "verification_report": {"passed": True},
        "license_scan": {"passed": True},
        "secret_scan": {"passed": True},
        "provenance_hit": False,
    }
    for where in ("gen", "verification"):
        _write(
            repo_root / where / "foo" / ".provenance.json",
            json.dumps(manifest, indent=2) + "\n",
        )


@pytest.fixture
def con(tmp_path):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root)
    connection = duckdb.connect()
    connection.execute("INSTALL yaml FROM community")
    connection.execute("LOAD yaml")
    graph_query_engine.load_views(connection, repo_root)
    try:
        yield connection
    finally:
        connection.close()


def test_prose_quoted_fields_produce_no_decision_edges(con):
    rows = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE source_id = 'D3' AND edge_type IN ('supersedes', 'builds_on')"
    ).fetchall()
    assert rows == [], (
        "D3 declares neither supersedes nor builds_on in frontmatter, "
        f"yet edges returned: {rows!r}"
    )

    # Also no edge anywhere sourced from D3's prose, whatever its source_id.
    stray = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE edge_type = 'supersedes'"
    ).fetchall()
    assert stray == [], f"no decision declares supersedes, got: {stray!r}"


def test_frontmatter_builds_on_list_yields_exactly_its_rows(con):
    rows = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE source_id = 'D4'"
    ).fetchall()
    normalized = sorted(tuple(str(v) for v in row) for row in rows)
    assert normalized == [
        ("D4", "D1", "builds_on"),
        ("D4", "D2", "builds_on"),
    ], f"unexpected edges for D4: {rows!r}"

    # The only builds_on rows in the whole corpus are D4's two.
    all_builds_on = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE edge_type = 'builds_on'"
    ).fetchall()
    assert sorted(tuple(str(v) for v in r) for r in all_builds_on) == [
        ("D4", "D1", "builds_on"),
        ("D4", "D2", "builds_on"),
    ], f"unexpected builds_on edges: {all_builds_on!r}"