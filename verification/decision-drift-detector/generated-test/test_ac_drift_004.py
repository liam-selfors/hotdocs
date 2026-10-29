import subprocess
import tempfile
from pathlib import Path


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_ac_drift_004_graph_query_engine_resolved_relative_to_repo_root():
    with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as log_dir:
        repo_root = Path(repo_dir)
        call_log = Path(log_dir) / "load_views_calls.log"
        call_log_repr = repr(str(call_log))

        gen_dir = repo_root / "gen" / "graph-query-engine"
        gen_dir.mkdir(parents=True)

        # The real loader creates a fresh module object per load, so the test
        # can't reach it via sys.modules; the fake records invocations to a
        # file instead, which the test reads back after the run completes.
        fake_src = f'''CALL_LOG = {call_log_repr}

def load_views(con, repo_root):
    with open(CALL_LOG, "a", encoding="utf-8") as f:
        f.write(str(repo_root) + "\\n")
    con.execute(
        "CREATE OR REPLACE VIEW nodes AS SELECT "
        "CAST(NULL AS VARCHAR) AS id, "
        "CAST(NULL AS VARCHAR) AS title, "
        "CAST(NULL AS VARCHAR) AS status, "
        "CAST(NULL AS VARCHAR) AS kind, "
        "CAST(NULL AS VARCHAR) AS owner_component_id "
        "WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW edges AS SELECT "
        "CAST(NULL AS VARCHAR) AS source_id, "
        "CAST(NULL AS VARCHAR) AS target_id, "
        "CAST(NULL AS VARCHAR) AS edge_type "
        "WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW decision_lineage AS SELECT "
        "CAST(NULL AS VARCHAR) AS id, "
        "CAST(NULL AS VARCHAR) AS last_ratified_commit "
        "WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW component_docs AS SELECT "
        "CAST(NULL AS VARCHAR) AS id, "
        "CAST(NULL AS VARCHAR) AS title, "
        "CAST(NULL AS VARCHAR) AS status, "
        "CAST(NULL AS VARCHAR) AS body "
        "WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW component_context AS SELECT "
        "CAST(NULL AS VARCHAR) AS component_id, "
        "CAST(NULL AS VARCHAR) AS purpose "
        "WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW component_provenance AS SELECT "
        "CAST(NULL AS VARCHAR) AS component_id, "
        "CAST(NULL AS VARCHAR) AS spec_bundle_hash, "
        "CAST(NULL AS BOOLEAN) AS provenance_hit "
        "WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW component_size AS SELECT "
        "CAST(NULL AS VARCHAR) AS component_id, "
        "CAST(NULL AS BIGINT) AS word_count "
        "WHERE FALSE"
    )
'''
        (gen_dir / "graph_query_engine.py").write_text(fake_src, encoding="utf-8")

        subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_root, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=repo_root, check=True, capture_output=True,
        )
        subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=repo_root, check=True, capture_output=True,
        )

        import decision_drift_detector

        decision_drift_detector.find_decision_drift(repo_root)

        assert call_log.exists(), "fake graph-query-engine's load_views was never called"
        calls = call_log.read_text(encoding="utf-8").splitlines()
        assert len(calls) == 1, (
            f"expected load_views to be called exactly once against repo_root, "
            f"got {len(calls)} call(s): {calls}"
        )