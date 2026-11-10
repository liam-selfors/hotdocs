import json
from pathlib import Path

import duckdb

import corpus_loader


FAKE_GQE_SOURCE = """
import json
from pathlib import Path


def load_views(con, repo_root):
    repo_root = Path(repo_root)
    log_path = Path(__file__).parent / "invocation_log.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"repo_root": str(repo_root)}) + "\\n")

    components_dir = repo_root / "specs" / "components"
    rows = []
    if components_dir.is_dir():
        for comp_dir in sorted(components_dir.iterdir()):
            comp_md = comp_dir / "component.md"
            if not comp_md.is_file():
                continue
            text = comp_md.read_text(encoding="utf-8")
            comp_id = None
            title = None
            status = None
            if text.startswith("---"):
                lines = text.splitlines()
                for line in lines[1:]:
                    if line.strip() == "---":
                        break
                    if ":" not in line:
                        continue
                    key, _, value = line.partition(":")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key == "id":
                        comp_id = value
                    elif key == "title":
                        title = value
                    elif key == "status":
                        status = value
            if comp_id:
                rows.append((comp_id, title, status))

    con.execute("DROP VIEW IF EXISTS nodes")
    con.execute("DROP TABLE IF EXISTS _fake_nodes_data")
    con.execute(
        "CREATE TABLE _fake_nodes_data (id TEXT, title TEXT, status TEXT, "
        "kind TEXT, owner_component_id TEXT)"
    )
    for comp_id, title, status in rows:
        con.execute(
            "INSERT INTO _fake_nodes_data VALUES (?, ?, ?, 'component', NULL)",
            [comp_id, title, status],
        )
    con.execute("CREATE VIEW nodes AS SELECT * FROM _fake_nodes_data")

    con.execute("DROP VIEW IF EXISTS edges")
    con.execute(
        "CREATE VIEW edges AS SELECT NULL::VARCHAR AS source_id, "
        "NULL::VARCHAR AS target_id, NULL::VARCHAR AS edge_type WHERE FALSE"
    )

    con.execute("DROP VIEW IF EXISTS component_docs")
    con.execute(
        "CREATE VIEW component_docs AS SELECT id AS id, title, status, "
        "'' AS body FROM nodes WHERE kind = 'component'"
    )

    con.execute("DROP VIEW IF EXISTS component_context")
    con.execute(
        "CREATE VIEW component_context AS SELECT id AS component_id, "
        "'' AS purpose FROM nodes WHERE kind = 'component'"
    )

    con.execute("DROP VIEW IF EXISTS component_provenance")
    con.execute(
        "CREATE VIEW component_provenance AS SELECT NULL::VARCHAR AS component_id, "
        "NULL::VARCHAR AS spec_bundle_hash WHERE FALSE"
    )

    con.execute("DROP VIEW IF EXISTS component_size")
    con.execute(
        "CREATE VIEW component_size AS SELECT NULL::VARCHAR AS component_id, "
        "NULL::BIGINT AS word_count WHERE FALSE"
    )

    con.execute("DROP VIEW IF EXISTS decision_lineage")
    con.execute(
        "CREATE VIEW decision_lineage AS SELECT NULL::VARCHAR AS id, "
        "NULL::VARCHAR AS last_ratified_commit WHERE FALSE"
    )
"""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_repo_root(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"

    component_md = """---
id: comp-foo
title: Foo
status: ratified
owners: [alice]
sealed: true
source_path: fake/foo.py
last_ratified_commit: 0000000000000000000000000000000000000000
---

## Purpose

Does foo things.
"""
    _write(repo_root / "specs" / "components" / "foo" / "component.md", component_md)

    requirement_md = """# R-FOO-001

**R-FOO-001** -- Foo MUST foo.
"""
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        requirement_md,
    )

    acceptance_md = """Covers: R-FOO-001

```gherkin
Given foo
When foo runs
Then foo happens
```
"""
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        acceptance_md,
    )

    gqe_module_path = repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py"
    _write(gqe_module_path, FAKE_GQE_SOURCE)

    return repo_root


def test_load_corpus_graph_has_one_component_node(tmp_path):
    repo_root = _build_repo_root(tmp_path)

    corpus = corpus_loader.load_corpus(repo_root)

    graph = corpus.get("graph") if isinstance(corpus, dict) else getattr(corpus, "graph", None)

    assert graph is not None
    assert isinstance(graph, duckdb.DuckDBPyConnection)

    result = graph.execute(
        "SELECT count(*) FROM nodes WHERE kind = 'component'"
    ).fetchone()
    assert result[0] == 1

    log_path = repo_root / "gen" / "graph-query-engine" / "invocation_log.jsonl"
    assert log_path.is_file()
    with open(log_path, "r", encoding="utf-8") as f:
        entries = [json.loads(line) for line in f if line.strip()]
    assert any(Path(entry["repo_root"]) == repo_root for entry in entries)