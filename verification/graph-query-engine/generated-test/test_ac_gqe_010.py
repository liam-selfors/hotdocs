import duckdb
import pytest

import graph_query_engine


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_repo(repo_root):
    _write(
        repo_root / "specs" / "components" / "dummy-component" / "component.md",
        "---\n"
        "id: comp-dummy-component\n"
        "title: Dummy Component\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "depends_on_guarantees: []\n"
        "sealed: true\n"
        "source_path: tools/dummy.py\n"
        "---\n\n"
        "# Dummy Component\n\n"
        "## Purpose\n\n"
        "Dummy component used only to keep corpus globs non-empty.\n",
    )

    _write(
        repo_root
        / "specs"
        / "components"
        / "dummy-component"
        / "acceptance"
        / "AC-DUMMY-001.md",
        "Covers: R-DUMMY-001\n\n"
        "```gherkin\n"
        "Given nothing\n"
        "When nothing happens\n"
        "Then nothing is asserted\n"
        "```\n",
    )

    _write(
        repo_root / "specs" / "product" / "dummy.md",
        "---\n"
        "id: P-DUMMY\n"
        "title: Dummy Capability\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n\n"
        "# Dummy Capability\n\n"
        "### CS-DUMMY-001\n"
        "Covers: R-DUMMY-001\n\n"
        "Some scenario prose.\n",
    )

    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Earlier decision one\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: abc123\n"
        "---\n\n"
        "Body text for D1.\n",
    )

    _write(
        repo_root / "specs" / "decisions" / "D2.md",
        "---\n"
        "id: D2\n"
        "title: Earlier decision two\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "last_ratified_commit: abc124\n"
        "---\n\n"
        "Body text for D2.\n",
    )

    _write(
        repo_root / "specs" / "decisions" / "D100.md",
        "---\n"
        "id: D100\n"
        "title: Decision that only quotes fields in prose\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n\n"
        "This decision's prose discusses an example from another document\n"
        "that said `supersedes: D1` and `builds_on: [D2]`, but this decision\n"
        "itself declares neither field in its own frontmatter.\n",
    )

    _write(
        repo_root / "specs" / "decisions" / "D101.md",
        "---\n"
        "id: D101\n"
        "title: Decision that builds on two priors\n"
        "status: draft\n"
        "owners: [alice]\n"
        "builds_on: [D1, D2]\n"
        "---\n\n"
        "This decision builds on D1 and D2.\n",
    )


def _connect():
    con = duckdb.connect()
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")
    return con


def test_quoted_prose_fields_produce_no_edge_rows(tmp_path):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root)

    con = _connect()
    graph_query_engine.load_views(con, repo_root)

    rows = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE source_id = 'D100' AND edge_type IN ('supersedes', 'builds_on')"
    ).fetchall()

    assert rows == []


def test_frontmatter_builds_on_list_produces_exact_edge_rows(tmp_path):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root)

    con = _connect()
    graph_query_engine.load_views(con, repo_root)

    rows = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE source_id = 'D101' AND edge_type = 'builds_on' "
        "ORDER BY target_id"
    ).fetchall()

    assert rows == [("D101", "D1", "builds_on"), ("D101", "D2", "builds_on")]