import tempfile
from pathlib import Path

import duckdb

import graph_query_engine


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_decision_supersedes_scalar_produces_nodes_and_edge():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        _write(
            repo_root / "specs" / "components" / "comp-x" / "component.md",
            "---\n"
            "id: comp-x\n"
            "title: Comp X\n"
            "status: draft\n"
            "owners: [alice]\n"
            "sealed: true\n"
            "source_path: fake/source/comp_x.py\n"
            "---\n\n"
            "# Comp X\n\n"
            "## Purpose\n\nFake component for testing.\n",
        )

        _write(
            repo_root / "specs" / "product" / "P-TEST-1.md",
            "---\n"
            "id: P-TEST-1\n"
            "title: Test Capability\n"
            "status: draft\n"
            "owners: [alice]\n"
            "---\n\n"
            "# Test Capability\n",
        )

        _write(
            repo_root / "specs" / "vars" / "VAR-TEST.md",
            "---\n"
            "id: VAR-TEST\n"
            "title: Test Var\n"
            "status: draft\n"
            "owners: [alice]\n"
            "---\n\n"
            "# Test Var\n",
        )

        _write(
            repo_root / "specs" / "decisions" / "D1.md",
            "---\n"
            "id: D1\n"
            "title: Decision One\n"
            "status: draft\n"
            "owners: [alice]\n"
            "supersedes: D2\n"
            "---\n\n"
            "# Decision One\n",
        )

        _write(
            repo_root / "specs" / "decisions" / "D2.md",
            "---\n"
            "id: D2\n"
            "title: Decision Two\n"
            "status: deprecated\n"
            "owners: [alice]\n"
            "---\n\n"
            "# Decision Two\n",
        )

        _write(
            repo_root
            / "specs"
            / "components"
            / "comp-x"
            / "interface"
            / "guarantees"
            / "G-1.md",
            "This guarantee holds.\n",
        )

        _write(
            repo_root / "specs" / "components" / "comp-x" / "requirements" / "R-1.md",
            "The component MUST do a thing.\n",
        )

        _write(
            repo_root / "specs" / "components" / "comp-x" / "acceptance" / "AC-1.md",
            "Covers: R-1\n\n"
            "```gherkin\n"
            "Given a thing\n"
            "When it happens\n"
            "Then it works\n"
            "```\n",
        )

        con = duckdb.connect(":memory:")
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")

        graph_query_engine.load_views(con, repo_root)

        node_rows = con.execute(
            "SELECT id, kind FROM nodes WHERE id IN ('D1', 'D2') ORDER BY id"
        ).fetchall()

        assert node_rows == [("D1", "decision"), ("D2", "decision")]

        edge_rows = con.execute(
            "SELECT source_id, target_id, edge_type FROM edges "
            "WHERE edge_type = 'supersedes'"
        ).fetchall()

        assert edge_rows == [("D1", "D2", "supersedes")]