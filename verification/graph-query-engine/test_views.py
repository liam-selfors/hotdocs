"""One test per AC-GQE-* criterion, verified against this repo's real
spec corpus — see conftest.py for why that's deliberate, not a
shortcut."""

import re
from pathlib import Path

import duckdb

from conftest import REPO_ROOT


def test_ac_gqe_001_nodes_counts_match_filesystem(con):
    counts = dict(con.execute("SELECT kind, count(*) FROM nodes GROUP BY 1").fetchall())
    assert counts["component"] == len(list((REPO_ROOT / "specs/components").glob("*/component.md")))
    assert counts["capability"] == len(list((REPO_ROOT / "specs/product").glob("*.md"))) - 1  # minus README.md
    assert counts["var"] == len(list((REPO_ROOT / "specs/vars").glob("*.md"))) - 1  # minus README.md
    assert counts["requirement"] == len(list((REPO_ROOT / "specs/components").glob("*/requirements/*.md")))
    assert counts["acceptance"] == len(list((REPO_ROOT / "specs/components").glob("*/acceptance/*.md")))
    assert counts["guarantee"] == len(list((REPO_ROOT / "specs/components").glob("*/interface/guarantees/*.md")))
    cs_count = 0
    for p in (REPO_ROOT / "specs/product").glob("*.md"):
        if p.name == "README.md":
            continue
        cs_count += len(re.findall(r"^### (CS-[A-Za-z0-9-]+)", p.read_text(), re.MULTILINE))
    assert counts["capability_scenario"] == cs_count


def test_ac_gqe_002_edges_counts_match_frontmatter(con):
    counts = dict(con.execute("SELECT edge_type, count(*) FROM edges GROUP BY 1").fetchall())
    totals = {"depends_on": 0, "realizes": 0, "uses_var": 0, "depends_on_guarantees": 0}
    for p in (REPO_ROOT / "specs/components").glob("*/component.md"):
        text = p.read_text()
        for field in totals:
            m = re.search(rf"^{field}:\s*\[(.*?)\]", text, re.MULTILINE)
            if m:
                totals[field] += len([x for x in m.group(1).split(",") if x.strip()])
    for field, expected in totals.items():
        assert counts.get(field, 0) == expected, field
    covers_count = len(list((REPO_ROOT / "specs/components").glob("*/acceptance/*.md")))
    for p in (REPO_ROOT / "specs/product").glob("*.md"):
        if p.name == "README.md":
            continue
        covers_count += len(re.findall(r"^### CS-[A-Za-z0-9-]+\s*\nCovers:", p.read_text(), re.MULTILINE))
    assert counts["covers"] == covers_count


def test_ac_gqe_003_component_docs_row_count_and_fields(con):
    n = con.execute("SELECT count(*) FROM component_docs").fetchone()[0]
    assert n == len(list((REPO_ROOT / "specs/components").glob("*/component.md")))
    row = con.execute(
        "SELECT id, title, status, body FROM component_docs WHERE id = 'comp-cache-manager'"
    ).fetchone()
    assert row[0] == "comp-cache-manager"
    assert row[1] == "Cache Manager"
    assert "## Purpose" in row[3]


def test_ac_gqe_004_component_context_multiline_purpose(con):
    purpose = con.execute(
        "SELECT purpose FROM component_context WHERE component_id = 'comp-cache-manager'"
    ).fetchone()[0]
    assert purpose.strip() != ""
    assert "\n" in purpose.strip()  # genuinely multi-line, not truncated to one line


def test_ac_gqe_005_component_provenance_degrades_empty(con):
    # This repo has no real pipeline runs yet (no generator exists) --
    # confirms the degrade-to-empty path (R-GQE-005), not a live file.
    assert not any(REPO_ROOT.glob("verification/*/.provenance.json"))
    n = con.execute("SELECT count(*) FROM component_provenance").fetchone()[0]
    assert n == 0
    # The view must still have every documented column, queryable, just empty.
    cols = {d[0] for d in con.execute("DESCRIBE component_provenance").fetchall()}
    assert {"component_id", "verification_report", "license_scan", "secret_scan", "provenance_hit"} <= cols


def test_ac_gqe_006_component_size_matches_spec_linter(con):
    sys_path_added = str(REPO_ROOT / "gen" / "spec-linter")
    import sys
    if sys_path_added not in sys.path:
        sys.path.insert(0, sys_path_added)
    import spec_linter
    corpus = spec_linter.load_corpus(REPO_ROOT)
    expected = spec_linter._size_measurements(corpus)
    rows = con.execute("SELECT component_id, word_count FROM component_size").fetchall()
    actual = dict(rows)
    for name, dims in expected.items():
        assert actual.get(name) == dims["component_doc_words"], name


def test_ac_gqe_007_load_views_idempotent(con):
    before = con.execute("SELECT count(*) FROM nodes").fetchone()[0]
    from graph_query_engine import load_views
    load_views(con, REPO_ROOT)
    after = con.execute("SELECT count(*) FROM nodes").fetchone()[0]
    assert before == after


def test_ac_gqe_008_decision_lineage_reflects_real_d31_d17_supersession(con):
    """D88 -- decision_lineage must surface the one real supersedes
    relationship this corpus actually has (D87, formalized under D88)."""
    rows = con.execute(
        "SELECT id, status, supersedes FROM decision_lineage WHERE id IN ('D17', 'D31')"
    ).fetchall()
    by_id = {r[0]: r for r in rows}
    assert by_id["D31"][2] == "D17"  # supersedes column
    assert by_id["D17"][1] == "deprecated"  # status column


def test_ac_gqe_008_supersedes_is_null_not_empty_string(con):
    rows = con.execute(
        "SELECT supersedes FROM decision_lineage WHERE id = 'D44'"
    ).fetchall()
    assert rows[0][0] is None
