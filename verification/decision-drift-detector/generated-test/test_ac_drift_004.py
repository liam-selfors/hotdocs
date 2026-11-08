import subprocess
from pathlib import Path

import decision_drift_detector


def test_graph_query_engine_resolved_relative_to_repo_root_not_module_location(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    subprocess.run(["git", "init"], cwd=str(repo_root), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "lselfors@gmail.com"],
        cwd=str(repo_root), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test Author"],
        cwd=str(repo_root), check=True, capture_output=True,
    )
    (repo_root / "specs").mkdir()
    (repo_root / "README.md").write_text("fixture repo root for AC-DRIFT-004\n")
    subprocess.run(["git", "add", "-A"], cwd=str(repo_root), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(repo_root), check=True, capture_output=True,
    )

    log_path = tmp_path / "load_views_calls.log"

    fake_dir = repo_root / "gen" / "graph-query-engine"
    fake_dir.mkdir(parents=True)
    fake_module_path = fake_dir / "graph_query_engine.py"

    lines = [
        "_LOG_PATH = " + repr(str(log_path)),
        "",
        "def load_views(con, repo_root):",
        "    with open(_LOG_PATH, 'a') as handle:",
        "        handle.write(str(repo_root) + chr(10))",
        "",
        "    con.execute(",
        "        'CREATE OR REPLACE VIEW nodes AS '",
        "        'SELECT CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS title, '",
        "        'CAST(NULL AS VARCHAR) AS status, CAST(NULL AS VARCHAR) AS kind, '",
        "        'CAST(NULL AS VARCHAR) AS owner_component_id WHERE FALSE'",
        "    )",
        "    con.execute(",
        "        'CREATE OR REPLACE VIEW edges AS '",
        "        'SELECT CAST(NULL AS VARCHAR) AS source_id, CAST(NULL AS VARCHAR) AS target_id, '",
        "        'CAST(NULL AS VARCHAR) AS edge_type WHERE FALSE'",
        "    )",
        "    con.execute(",
        "        'CREATE OR REPLACE VIEW component_docs AS '",
        "        'SELECT CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS title, '",
        "        'CAST(NULL AS VARCHAR) AS status, CAST(NULL AS VARCHAR) AS body WHERE FALSE'",
        "    )",
        "    con.execute(",
        "        'CREATE OR REPLACE VIEW component_context AS '",
        "        'SELECT CAST(NULL AS VARCHAR) AS component_id, CAST(NULL AS VARCHAR) AS purpose '",
        "        'WHERE FALSE'",
        "    )",
        "    con.execute(",
        "        'CREATE OR REPLACE VIEW component_provenance AS '",
        "        'SELECT CAST(NULL AS VARCHAR) AS component_id, CAST(NULL AS VARCHAR) AS spec_bundle_hash, '",
        "        'CAST(NULL AS VARCHAR) AS verification_report, CAST(NULL AS VARCHAR) AS license_scan, '",
        "        'CAST(NULL AS VARCHAR) AS secret_scan, CAST(NULL AS BOOLEAN) AS provenance_hit '",
        "        'WHERE FALSE'",
        "    )",
        "    con.execute(",
        "        'CREATE OR REPLACE VIEW component_size AS '",
        "        'SELECT CAST(NULL AS VARCHAR) AS component_id, CAST(NULL AS BIGINT) AS word_count '",
        "        'WHERE FALSE'",
        "    )",
        "    con.execute(",
        "        'CREATE OR REPLACE VIEW decision_lineage AS '",
        "        'SELECT CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS last_ratified_commit '",
        "        'WHERE FALSE'",
        "    )",
        "",
    ]
    fake_module_path.write_text("\n".join(lines))

    dd_file = getattr(decision_drift_detector, "__file__", None)
    if dd_file is not None:
        dd_path = Path(dd_file).resolve()
        assert dd_path != fake_module_path.resolve()
        assert dd_path != repo_root.resolve()
        assert repo_root.resolve() not in dd_path.parents

    report = decision_drift_detector.find_decision_drift(repo_root)

    entries = report.get("entries") if isinstance(report, dict) else getattr(report, "entries", None)
    assert isinstance(entries, list)

    assert log_path.exists(), "fake graph-query-engine.load_views was never invoked"
    calls = [line for line in log_path.read_text().splitlines() if line.strip()]
    assert len(calls) == 1, f"expected load_views called exactly once, got {len(calls)}: {calls}"
    assert Path(calls[0]).resolve() == repo_root.resolve()