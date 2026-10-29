import subprocess
import tempfile
from pathlib import Path

import decision_drift_detector


def field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _run_git(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, capture_output=True)


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


FAKE_GRAPH_QUERY_ENGINE = '''
def load_views(con, repo_root):
    con.execute("""
        CREATE OR REPLACE VIEW nodes AS SELECT * FROM (VALUES
            ('D1', 'Retry cap fixed at 3', 'ratified', 'decision', CAST(NULL AS VARCHAR)),
            ('D2', 'Retry cap raised to 5', 'ratified', 'decision', CAST(NULL AS VARCHAR))
        ) AS t(id, title, status, kind, owner_component_id)
    """)
    con.execute("""
        CREATE OR REPLACE VIEW edges AS SELECT * FROM (VALUES
            ('D2', 'D1', 'supersedes')
        ) AS t(source_id, target_id, edge_type)
    """)
    con.execute("""
        CREATE OR REPLACE VIEW decision_lineage AS SELECT * FROM (VALUES
            ('D1', 'aaaaaaa'),
            ('D2', 'bbbbbbb')
        ) AS t(id, last_ratified_commit)
    """)
    con.execute("""
        CREATE OR REPLACE VIEW component_docs AS SELECT
            CAST(NULL AS VARCHAR) AS id,
            CAST(NULL AS VARCHAR) AS title,
            CAST(NULL AS VARCHAR) AS status,
            CAST(NULL AS VARCHAR) AS body
        WHERE FALSE
    """)
    con.execute("""
        CREATE OR REPLACE VIEW component_context AS SELECT
            CAST(NULL AS VARCHAR) AS component_id,
            CAST(NULL AS VARCHAR) AS purpose
        WHERE FALSE
    """)
    con.execute("""
        CREATE OR REPLACE VIEW component_provenance AS SELECT
            CAST(NULL AS VARCHAR) AS component_id
        WHERE FALSE
    """)
    con.execute("""
        CREATE OR REPLACE VIEW component_size AS SELECT
            CAST(NULL AS VARCHAR) AS component_id,
            CAST(NULL AS BIGINT) AS word_count
        WHERE FALSE
    """)
'''


def test_ac_drift_003():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        _run_git(["init", "-q"], repo_root)
        _run_git(["config", "user.email", "lselfors@gmail.com"], repo_root)
        _run_git(["config", "user.name", "lselfors"], repo_root)
        _run_git(["config", "commit.gpgsign", "false"], repo_root)

        _write(
            repo_root / "specs" / "decisions" / "D1.md",
            "---\n"
            "id: D1\n"
            "title: Retry cap fixed at 3\n"
            "status: ratified\n"
            "owners: [lselfors]\n"
            "last_ratified_commit: 0000000\n"
            "---\n\n"
            "Retries are capped at 3 attempts.\n",
        )
        _run_git(["add", "-A"], repo_root)
        _run_git(["commit", "-q", "-m", "Add D1"], repo_root)

        _write(
            repo_root / "specs" / "components" / "widget" / "component.md",
            "---\n"
            "id: comp-widget\n"
            "title: Widget\n"
            "status: draft\n"
            "owners: [lselfors]\n"
            "sealed: true\n"
            "source_path: fake/widget.py\n"
            "---\n\n"
            "# Purpose\n\n"
            "Widget demonstrates retry behavior.\n",
        )
        _write(
            repo_root / "specs" / "components" / "widget" / "requirements" / "R-WIDGET-001.md",
            "# R-WIDGET-001\n\n"
            "Widget retries requests with a cap documented in decision D1.\n",
        )
        _write(
            repo_root / "specs" / "components" / "widget" / "acceptance" / "AC-WIDGET-001.md",
            "# AC-WIDGET-001\n\n"
            "Covers: R-WIDGET-001\n\n"
            "Given a request fails\n"
            "When the retry cap from D1 is reached\n"
            "Then the widget stops retrying\n",
        )
        _run_git(["add", "-A"], repo_root)
        _run_git(["commit", "-q", "-m", "Add widget component citing D1"], repo_root)

        _write(
            repo_root / "specs" / "decisions" / "D2.md",
            "---\n"
            "id: D2\n"
            "title: Retry cap raised to 5\n"
            "status: ratified\n"
            "owners: [lselfors]\n"
            "last_ratified_commit: 0000000\n"
            "supersedes: [D1]\n"
            "---\n\n"
            "Raises the retry cap set by D1 to 5 attempts.\n",
        )
        _run_git(["add", "-A"], repo_root)
        _run_git(["commit", "-q", "-m", "Add D2 superseding D1"], repo_root)

        fake_module_path = repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py"
        _write(fake_module_path, FAKE_GRAPH_QUERY_ENGINE)

        report = decision_drift_detector.find_decision_impact(repo_root, "D1")

        dependent_decisions = field(report, "dependent_decisions", [])
        citing_files = [str(f).replace("\\", "/") for f in field(report, "citing_files", [])]

        assert "D2" in dependent_decisions
        assert "specs/components/widget/requirements/R-WIDGET-001.md" in citing_files