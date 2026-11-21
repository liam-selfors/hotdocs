# hotdocs-criterion: sha256:e197c1a96024297b7885d74034ccd0dcb4587844748f97056d1a6d52581aea32
import subprocess
from pathlib import Path

import decision_drift_detector


GIT_CFG = [
    "-c", "user.name=t",
    "-c", "user.email=t@t",
    "-c", "commit.gpgsign=false",
]


def git(repo_root, *args):
    subprocess.run(
        ["git"] + GIT_CFG + list(args),
        cwd=str(repo_root),
        check=True,
        capture_output=True,
    )


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_fake_graph_query_engine(repo_root, log_path):
    fake_dir = repo_root / "gen" / "graph-query-engine"
    fake_dir.mkdir(parents=True)
    views = [
        "CREATE OR REPLACE VIEW nodes AS SELECT "
        "CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS title, "
        "CAST(NULL AS VARCHAR) AS status, CAST(NULL AS VARCHAR) AS kind, "
        "CAST(NULL AS VARCHAR) AS owner_component_id WHERE 1 = 0",
        "CREATE OR REPLACE VIEW edges AS SELECT "
        "CAST(NULL AS VARCHAR) AS source_id, CAST(NULL AS VARCHAR) AS target_id, "
        "CAST(NULL AS VARCHAR) AS edge_type WHERE 1 = 0",
        "CREATE OR REPLACE VIEW component_docs AS SELECT "
        "CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS title, "
        "CAST(NULL AS VARCHAR) AS status, CAST(NULL AS VARCHAR) AS body WHERE 1 = 0",
        "CREATE OR REPLACE VIEW component_context AS SELECT "
        "CAST(NULL AS VARCHAR) AS component_id, CAST(NULL AS VARCHAR) AS purpose WHERE 1 = 0",
        "CREATE OR REPLACE VIEW component_provenance AS SELECT "
        "CAST(NULL AS VARCHAR) AS component_id, CAST(NULL AS VARCHAR) AS spec_bundle_hash, "
        "CAST(NULL AS BOOLEAN) AS provenance_hit WHERE 1 = 0",
        "CREATE OR REPLACE VIEW component_size AS SELECT "
        "CAST(NULL AS VARCHAR) AS component_id, CAST(NULL AS BIGINT) AS word_count WHERE 1 = 0",
        "CREATE OR REPLACE VIEW decision_lineage AS SELECT "
        "CAST(NULL AS VARCHAR) AS id, CAST(NULL AS VARCHAR) AS last_ratified_commit WHERE 1 = 0",
    ]
    src = ""
    src += "LOG = " + repr(str(log_path)) + "\n"
    src += "VIEWS = " + repr(views) + "\n"
    src += "\n"
    src += "def load_views(con, repo_root):\n"
    src += "    with open(LOG, 'a') as f:\n"
    src += "        f.write(str(repo_root) + chr(10))\n"
    src += "    for sql in VIEWS:\n"
    src += "        con.execute(sql)\n"
    src += "    return None\n"
    (fake_dir / "graph_query_engine.py").write_text(src)


def test_ac_drift_004_graph_query_engine_resolved_from_repo_root(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "load_views_calls.log"

    # The component's own code must live somewhere else entirely.
    own_file = Path(decision_drift_detector.__file__).resolve()
    assert repo_root.resolve() not in own_file.parents

    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "D1.md").write_text(
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# D1\n"
    )

    write_fake_graph_query_engine(repo_root, log_path)

    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "initial")

    report = decision_drift_detector.find_decision_drift(repo_root)
    entries = field(report, "entries")
    assert isinstance(list(entries), list)

    assert log_path.is_file(), (
        "fake load_views under repo_root/gen/graph-query-engine was never "
        "called; graph-query-engine was not resolved relative to repo_root"
    )
    calls = [line for line in log_path.read_text().splitlines() if line.strip()]
    assert len(calls) == 1, calls