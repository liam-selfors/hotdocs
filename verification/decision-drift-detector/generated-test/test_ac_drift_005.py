import json
import os
import subprocess
from pathlib import Path

import pytest

import decision_drift_detector


FAKE_GQE_SOURCE = '''
def load_views(con, repo_root):
    con.execute(
        """
        CREATE OR REPLACE VIEW nodes AS
        SELECT CAST(NULL AS VARCHAR) AS id,
               CAST(NULL AS VARCHAR) AS title,
               CAST(NULL AS VARCHAR) AS status,
               CAST(NULL AS VARCHAR) AS kind,
               CAST(NULL AS VARCHAR) AS owner_component_id
        FROM (SELECT 1) AS _t
        WHERE FALSE
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW edges AS
        SELECT CAST(NULL AS VARCHAR) AS source_id,
               CAST(NULL AS VARCHAR) AS target_id,
               CAST(NULL AS VARCHAR) AS edge_type
        FROM (SELECT 1) AS _t
        WHERE FALSE
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW component_docs AS
        SELECT CAST(NULL AS VARCHAR) AS id,
               CAST(NULL AS VARCHAR) AS title,
               CAST(NULL AS VARCHAR) AS status,
               CAST(NULL AS VARCHAR) AS body
        FROM (SELECT 1) AS _t
        WHERE FALSE
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW component_context AS
        SELECT CAST(NULL AS VARCHAR) AS component_id,
               CAST(NULL AS VARCHAR) AS purpose
        FROM (SELECT 1) AS _t
        WHERE FALSE
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW component_provenance AS
        SELECT CAST(NULL AS VARCHAR) AS component_id,
               CAST(NULL AS VARCHAR) AS spec_bundle_hash,
               CAST(NULL AS BOOLEAN) AS provenance_hit
        FROM (SELECT 1) AS _t
        WHERE FALSE
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW component_size AS
        SELECT CAST(NULL AS VARCHAR) AS component_id,
               CAST(NULL AS BIGINT) AS word_count
        FROM (SELECT 1) AS _t
        WHERE FALSE
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW decision_lineage AS
        SELECT CAST(NULL AS VARCHAR) AS id,
               CAST(NULL AS VARCHAR) AS last_ratified_commit
        FROM (SELECT 1) AS _t
        WHERE FALSE
        """
    )
'''


def _init_git_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    (root / "README.md").write_text("fixture repo\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=root, check=True)


def _install_fake_graph_query_engine(repo_root: Path) -> None:
    dep_dir = repo_root / "gen" / "graph-query-engine"
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / "graph_query_engine.py").write_text(FAKE_GQE_SOURCE)


def _make_drift_free_repo(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    _init_git_repo(root)
    _install_fake_graph_query_engine(root)
    return root


def test_decision_drift_json_no_drift_returns_0_with_empty_entries(tmp_path, capsys):
    repo = _make_drift_free_repo(tmp_path, "repo_json")

    exit_code = decision_drift_detector.main(
        ["decision-drift", f"--repo-root={repo}", "--format=json"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    report = json.loads(captured.out)
    assert report["entries"] == []


def test_decision_impact_human_readable_returns_0(tmp_path, capsys):
    repo = _make_drift_free_repo(tmp_path, "repo_impact")

    exit_code = decision_drift_detector.main(
        ["decision-impact", "D1", f"--repo-root={repo}"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "D1" in captured.out
    with pytest.raises(json.JSONDecodeError):
        json.loads(captured.out)


def test_decision_impact_missing_decision_id_returns_2(tmp_path):
    repo = _make_drift_free_repo(tmp_path, "repo_missing_id")

    exit_code = decision_drift_detector.main(
        ["decision-impact", f"--repo-root={repo}"]
    )

    assert exit_code == 2


def test_decision_drift_non_git_repo_root_returns_2(tmp_path):
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()

    exit_code = decision_drift_detector.main(
        ["decision-drift", f"--repo-root={not_a_repo}"]
    )

    assert exit_code == 2


def test_decision_drift_defaults_repo_root_to_cwd_git_root(tmp_path):
    repo = _make_drift_free_repo(tmp_path, "repo_cwd_default")
    original_cwd = Path.cwd()
    os.chdir(repo)
    try:
        exit_code = decision_drift_detector.main(["decision-drift"])
    finally:
        os.chdir(original_cwd)

    assert exit_code == 0


def test_decision_drift_bogus_format_returns_2(tmp_path):
    repo = _make_drift_free_repo(tmp_path, "repo_bogus_format")

    exit_code = decision_drift_detector.main(
        ["decision-drift", f"--repo-root={repo}", "--format=bogus"]
    )

    assert exit_code == 2