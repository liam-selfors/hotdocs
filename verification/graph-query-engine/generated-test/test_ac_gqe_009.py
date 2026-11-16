"""AC-GQE-009 (Covers: R-GQE-001).

Given a repo root with one component and two decision records: D1, whose
frontmatter has the scalar line "supersedes: D2" (a single id, never a
list), and D2, whose status is "deprecated"
When load_views runs
Then nodes contains a row for each decision, both kind "decision", and
edges contains exactly the row (D1, D2, "supersedes").
"""

import json
from pathlib import Path

import duckdb
import pytest

import graph_query_engine


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    # --- the one component (sealed; every list-valued field present, empty) ---
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "depends_on_guarantees: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does a small, well-defined thing for testing.\n"
        "\n"
        "## Notes\n"
        "\n"
        "Nothing else to say.\n",
    )
    _write(
        comp_dir / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n\nFoo always returns a value.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST return a value.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given foo\n"
        "When it runs\n"
        "Then it returns a value\n"
        "```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    # --- supporting corpus files so every glob has at least one match ---
    _write(
        repo_root / "specs" / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Foo capability\n"
        "\n"
        "Describes foo.\n",
    )
    _write(
        repo_root / "specs" / "vars" / "VAR-FOO.md",
        "---\n"
        "id: VAR-FOO\n"
        "title: Foo var\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# VAR-FOO\n"
        "\n"
        "A placeholder variable declaration.\n",
    )
    _write(
        repo_root / "gen" / "foo" / ".provenance.json",
        json.dumps(
            {
                "component_id": "comp-foo",
                "spec_bundle_hash": "sha256:0000",
                "verification_report": {"result": "pass"},
                "license_scan": {"result": "pass"},
                "secret_scan": {"result": "pass"},
                "provenance_hit": False,
            }
        ),
    )

    # --- the two decision records under test ---
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: ratified\n"
        "owners: [team]\n"
        "last_ratified_commit: abc1234\n"
        "supersedes: D2\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "Replaces D2.\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D2.md",
        "---\n"
        "id: D2\n"
        "title: Second decision\n"
        "status: deprecated\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# D2\n"
        "\n"
        "Superseded by D1.\n",
    )


@pytest.fixture
def loaded(tmp_path):
    repo_root = tmp_path.resolve() / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")

    graph_query_engine.load_views(con, repo_root)
    try:
        yield con
    finally:
        con.close()


def test_ac_gqe_009_scalar_supersedes_yields_decision_nodes_and_one_edge(loaded):
    con = loaded

    # --- nodes: one row per decision, each of kind "decision" ---
    rows = con.execute(
        "SELECT id, kind FROM nodes WHERE id IN ('D1', 'D2') ORDER BY id"
    ).fetchall()
    assert rows == [("D1", "decision"), ("D2", "decision")], rows

    decision_ids = sorted(
        r[0]
        for r in con.execute(
            "SELECT id FROM nodes WHERE kind = 'decision'"
        ).fetchall()
    )
    assert decision_ids == ["D1", "D2"], decision_ids

    # --- edges: exactly the (D1, D2, supersedes) row for these decisions ---
    decision_edges = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE source_id IN ('D1', 'D2') "
        "   OR target_id IN ('D1', 'D2') "
        "   OR edge_type IN ('supersedes', 'builds_on')"
    ).fetchall()
    assert [tuple(r) for r in decision_edges] == [("D1", "D2", "supersedes")], (
        decision_edges
    )