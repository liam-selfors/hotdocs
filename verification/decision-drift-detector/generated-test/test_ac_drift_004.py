# hotdocs-criterion: sha256:fc125744b8884ebd33db687af8c5c4f95c5fc80a858a31904e9d973fa5b53d44
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


def build_fake_graph_query_engine(repo_root, log_path):
    fake_dir = repo_root / "gen" / "graph-query-engine"
    fake_dir.mkdir(parents=True)
    sql_statements = [
        "CREATE OR REPLACE VIEW nodes AS SELECT * FROM (VALUES "
        "('D1', 'First decision', 'draft', 'decision', CAST(NULL AS TEXT))) "
        "AS t(id, title, status, kind, owner_component_id)",
        "CREATE OR REPLACE VIEW edges AS SELECT "
        "CAST(NULL AS TEXT) AS source_id, CAST(NULL AS TEXT) AS target_id, "
        "CAST(NULL AS TEXT) AS edge_type WHERE false",
        "CREATE OR REPLACE VIEW component_docs AS SELECT "
        "CAST(NULL AS TEXT) AS id, CAST(NULL AS TEXT) AS title, "
        "CAST(NULL AS TEXT) AS status, CAST(NULL AS TEXT) AS body WHERE false",
        "CREATE OR REPLACE VIEW component_context AS SELECT "
        "CAST(NULL AS TEXT) AS component_id, CAST(NULL AS TEXT) AS purpose "
        "WHERE false",
        "CREATE OR REPLACE VIEW component_provenance AS SELECT "
        "CAST(NULL AS TEXT) AS component_id, "
        "CAST(NULL AS TEXT) AS spec_bundle_hash, "
        "CAST(NULL AS STRUCT(result TEXT)) AS verification_report, "
        "CAST(NULL AS STRUCT(result TEXT)) AS license_scan, "
        "CAST(NULL AS STRUCT(result TEXT)) AS secret_scan, "
        "CAST(NULL AS BOOLEAN) AS provenance_hit WHERE false",
        "CREATE OR REPLACE VIEW component_size AS SELECT "
        "CAST(NULL AS TEXT) AS component_id, "
        "CAST(NULL AS BIGINT) AS word_count WHERE false",
        "CREATE OR REPLACE VIEW bundle_size AS SELECT "
        "CAST(NULL AS TEXT) AS component_id, "
        "CAST(NULL AS BIGINT) AS generator_words, "
        "CAST(NULL AS BIGINT) AS criterion_words_max WHERE false",
        "CREATE OR REPLACE VIEW decision_lineage AS SELECT * FROM (VALUES "
        "('D1', CAST(NULL AS TEXT))) AS t(id, last_ratified_commit)",
    ]
    source = (
        "SQL_STATEMENTS = " + repr(sql_statements) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def load_views(con, repo_root):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('load_views ' + str(repo_root) + '\\n')\n"
        "    for statement in SQL_STATEMENTS:\n"
        "        con.execute(statement)\n"
        "    return None\n"
    )
    (fake_dir / "graph_query_engine.py").write_text(source, encoding="utf-8")


def build_corpus(repo_root):
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
        "# D1\n",
        encoding="utf-8",
    )


def test_ac_drift_004_graph_query_engine_resolved_relative_to_repo_root(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "load_views_calls.log"

    # The component's own code must live outside repo_root entirely.
    own_file = Path(decision_drift_detector.__file__).resolve()
    resolved_root = repo_root.resolve()
    assert resolved_root not in own_file.parents

    build_fake_graph_query_engine(repo_root, log_path)
    build_corpus(repo_root)

    git(repo_root, "init", "-q")
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", "initial")

    report = decision_drift_detector.find_decision_drift(repo_root)

    entries = field(report, "entries")
    assert list(entries) == []

    assert log_path.is_file(), (
        "fake load_views under repo_root/gen/graph-query-engine was never "
        "called: graph-query-engine was not resolved relative to repo_root"
    )
    calls = [
        line for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(calls) == 1, calls