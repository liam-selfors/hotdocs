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


def test_ac_gqe_005_component_provenance_degrades_empty(tmp_path):
    """R-GQE-005 -- a corpus with no .provenance.json at all (a new
    project) still gets a queryable, correctly-shaped, empty view."""
    c = _synthetic_corpus(tmp_path, {})
    assert c.execute("SELECT count(*) FROM component_provenance").fetchone()[0] == 0
    cols = {d[0] for d in c.execute("DESCRIBE component_provenance").fetchall()}
    assert {"component_id", "verification_report", "license_scan", "secret_scan", "provenance_hit"} <= cols


def test_ac_gqe_005_component_provenance_reads_a_manifest(tmp_path):
    """R-GQE-005 -- one row per verification/<slug>/.provenance.json,
    keyed comp-<slug>."""
    manifest = tmp_path / "verification" / "foo" / ".provenance.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '{"spec_bundle_hash": "sha256:00", "model_pin": "m", "prompt_version": "v1",'
        ' "retry_feedback": null, "pipeline_version": "v1", "gate_versions": {},'
        ' "provenance_hit": false, "generated_at": "2026-01-01T00:00:00Z",'
        ' "verification_run_id": "r", "verification_report": {"overall": "pass"},'
        ' "license_scan": {}, "secret_scan": {}}'
    )
    c = _synthetic_corpus(tmp_path, {})
    rows = c.execute("SELECT component_id, provenance_hit FROM component_provenance").fetchall()
    assert rows == [("comp-foo", False)]


def test_ac_gqe_006_component_size_counts_words_after_frontmatter(con):
    """R-GQE-006 -- word_count is every whitespace-separated word in a
    component's .md files, frontmatter excluded, computed here
    independently of spec-linter (which reads this same view, D13)."""
    expected = {}
    for path in (REPO_ROOT / "specs" / "components").glob("*/**/*.md"):
        name = path.relative_to(REPO_ROOT / "specs" / "components").parts[0]
        text = re.sub(r"^---\n.*?\n---\n", "", path.read_text(encoding="utf-8"), count=1, flags=re.S)
        expected[name] = expected.get(name, 0) + len(text.split())
    actual = dict(con.execute("SELECT component_id, word_count FROM component_size").fetchall())
    assert actual == expected


def test_ac_gqe_007_load_views_idempotent(con):
    before = con.execute("SELECT count(*) FROM nodes").fetchone()[0]
    from graph_query_engine import load_views
    load_views(con, REPO_ROOT)
    after = con.execute("SELECT count(*) FROM nodes").fetchone()[0]
    assert before == after


def _synthetic_corpus(tmp_path, decisions: dict[str, str]):
    """A minimal corpus: one component (the component glob is the one
    deliberately unguarded, R-GQE-007) plus the given decision files."""
    comp = tmp_path / "specs" / "components" / "foo"
    comp.mkdir(parents=True)
    (comp / "component.md").write_text(
        "---\nid: comp-foo\ntitle: Foo\nstatus: draft\nowners: [t]\n---\n\n# Foo\n\n## Purpose\n\nX.\n\n## Next\n"
    )
    dec = tmp_path / "specs" / "decisions"
    dec.mkdir(parents=True)
    for name, text in decisions.items():
        (dec / f"{name}.md").write_text(text)
    c = duckdb.connect()
    c.execute("INSTALL yaml FROM community")
    c.execute("LOAD yaml")
    from graph_query_engine import load_views
    load_views(c, tmp_path)
    return c


def _decision(did, status="ratified", extra="", body="Body.", commit="abc1234"):
    commit_line = f"last_ratified_commit: {commit}\n" if commit else ""
    return f"---\nid: {did}\ntitle: T {did}\nstatus: {status}\nowners: [t]\n{extra}{commit_line}---\n\n# {did}\n\n{body}\n"


def test_ac_gqe_008_decision_lineage_has_last_ratified_commit(con):
    """R-GQE-008 -- decision_lineage is id/last_ratified_commit only;
    status/supersedes/builds_on live in nodes/edges. Real corpus."""
    rows = con.execute(
        "SELECT last_ratified_commit FROM decision_lineage WHERE id = 'D31'"
    ).fetchall()
    assert rows[0][0] is not None and len(rows[0][0]) > 0
    cols = [c[0] for c in con.execute("SELECT * FROM decision_lineage LIMIT 0").description]
    assert cols == ["id", "last_ratified_commit"]


def test_ac_gqe_008_missing_last_ratified_commit_is_null_not_empty(tmp_path):
    c = _synthetic_corpus(tmp_path, {
        "D1": _decision("D1", commit="abc1234"),
        "D2": _decision("D2", commit=None, body="Prose quoting last_ratified_commit: deadbeef is not a field."),
    })
    rows = dict(c.execute("SELECT id, last_ratified_commit FROM decision_lineage").fetchall())
    assert rows == {"D1": "abc1234", "D2": None}


def test_ac_gqe_009_decision_nodes_and_supersedes_edge(tmp_path):
    """R-GQE-001/002 -- decisions are kind='decision' nodes and supersedes
    is a real edge. Synthetic corpus: the real one has no supersession
    (the 0fb1d53 renumbering reset it to zero deprecations; this test
    once asserted the pre-renumbering D31-supersedes-D17 pair)."""
    c = _synthetic_corpus(tmp_path, {
        "D1": _decision("D1", status="deprecated"),
        "D2": _decision("D2", extra="supersedes: D1\n"),
    })
    rows = c.execute("SELECT id, status, kind FROM nodes WHERE kind = 'decision' ORDER BY id").fetchall()
    assert rows == [("D1", "deprecated", "decision"), ("D2", "ratified", "decision")]
    assert c.execute("SELECT source_id, target_id FROM edges WHERE edge_type = 'supersedes'").fetchall() == [("D2", "D1")]


def test_ac_gqe_010_prose_quoting_a_field_is_not_an_edge(tmp_path):
    c = _synthetic_corpus(tmp_path, {
        "D1": _decision("D1"),
        "D2": _decision("D2", body="We write `supersedes: D1` and\nbuilds_on: [D1] in prose, but declare neither."),
        "D3": _decision("D3", extra="builds_on: [D1, D2]\n"),
    })
    assert c.execute("SELECT * FROM edges WHERE edge_type IN ('supersedes', 'builds_on') AND source_id = 'D2'").fetchall() == []
    assert c.execute("SELECT source_id, target_id FROM edges WHERE edge_type = 'builds_on' ORDER BY target_id").fetchall() == [("D3", "D1"), ("D3", "D2")]


def test_ac_gqe_010_real_corpus_decision_edges_match_frontmatter(con):
    """The view must agree with an independent frontmatter-only parse of
    every real decision (D137 quotes `supersedes: [D17]` in prose)."""
    expected_builds, expected_supersedes = set(), set()
    for f in (REPO_ROOT / "specs/decisions").glob("D*.md"):
        fm = re.match(r"---\n(.*?)\n---\n", f.read_text(), re.S).group(1)
        did = re.search(r"^id:\s*(\S+)", fm, re.M).group(1)
        m = re.search(r"^builds_on:\s*\[(.*?)\]", fm, re.M)
        if m:
            expected_builds |= {(did, x.strip()) for x in m.group(1).split(",") if x.strip()}
        m = re.search(r"^supersedes:\s*(\S+)", fm, re.M)
        if m:
            expected_supersedes.add((did, m.group(1)))
    got_builds = set(con.execute("SELECT source_id, target_id FROM edges WHERE edge_type = 'builds_on'").fetchall())
    got_supersedes = set(con.execute("SELECT source_id, target_id FROM edges WHERE edge_type = 'supersedes'").fetchall())
    assert got_builds == expected_builds
    assert got_supersedes == expected_supersedes
    n = con.execute("SELECT count(*) FROM nodes WHERE kind = 'decision'").fetchone()[0]
    assert n == len(list((REPO_ROOT / "specs/decisions").glob("D*.md")))


def test_ac_gqe_009_no_supersedes_edge_for_unset_decisions(con):
    rows = con.execute(
        "SELECT * FROM edges WHERE edge_type = 'supersedes' AND source_id = 'D44'"
    ).fetchall()
    assert rows == []
