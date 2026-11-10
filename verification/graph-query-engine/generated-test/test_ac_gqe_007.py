import duckdb
import graph_query_engine


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "test-comp"
    _write(
        comp_dir / "component.md",
        """---
id: comp-test-comp
title: Test Comp
status: draft
owners: [alice]
depends_on: []
realizes: []
uses_var: []
sealed: true
source_path: fake/test-comp
---

# Test Comp

## Purpose

This is a test component used for AC-GQE-007.
""",
    )

    _write(
        comp_dir / "requirements" / "r-test-comp-001.md",
        """**R-TEST-COMP-001** — MUST do something.
""",
    )

    _write(
        comp_dir / "acceptance" / "ac-test-comp-001.md",
        """Covers: R-TEST-COMP-001

```gherkin
Given x
When y
Then z
```
""",
    )

    decisions_dir = repo_root / "specs" / "decisions"
    _write(
        decisions_dir / "D1.md",
        """---
id: D1
title: Test Decision
status: ratified
owners: [alice]
last_ratified_commit: abc123def
---

# D1

Some decision text.
""",
    )


_VIEWS = (
    "nodes",
    "edges",
    "component_docs",
    "component_context",
    "component_provenance",
    "component_size",
    "decision_lineage",
)


def _fetch_all_views(con):
    snapshot = {}
    for view in _VIEWS:
        cur = con.execute(f"SELECT * FROM {view}")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        snapshot[view] = (cols, rows)
    return snapshot


def test_load_views_is_idempotent(tmp_path):
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _build_fixture(repo_root)

    con = duckdb.connect(":memory:")
    con.execute("INSTALL yaml FROM community")
    con.execute("LOAD yaml")

    graph_query_engine.load_views(con, repo_root)
    first = _fetch_all_views(con)

    graph_query_engine.load_views(con, repo_root)
    second = _fetch_all_views(con)

    assert set(first.keys()) == set(second.keys())
    for view in first:
        first_cols, first_rows = first[view]
        second_cols, second_rows = second[view]
        assert first_cols == second_cols, f"{view} columns changed between calls"
        assert first_rows == second_rows, f"{view} rows changed between calls"

    assert len(first["nodes"][1]) > 0