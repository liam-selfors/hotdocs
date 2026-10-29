import subprocess

import decision_drift_detector


def field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def run_git(repo_root, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def git_commit(repo_root, message):
    run_git(
        repo_root,
        "-c", "user.name=Test Fixture",
        "-c", "user.email=test-fixture@example.com",
        "-c", "commit.gpgsign=false",
        "commit",
        "-m", message,
    )


FAKE_GRAPH_QUERY_ENGINE_MODULE = '''
from pathlib import Path

LOAD_VIEWS_CALLS = []


def load_views(con, repo_root):
    LOAD_VIEWS_CALLS.append(repo_root)
    Path(repo_root, ".load_views_called").write_text("called")
    con.execute(
        """
        CREATE OR REPLACE VIEW nodes AS
        SELECT * FROM (VALUES
            ('D17', CAST(NULL AS VARCHAR), 'deprecated', 'decision', CAST(NULL AS VARCHAR)),
            ('D31', CAST(NULL AS VARCHAR), 'ratified', 'decision', CAST(NULL AS VARCHAR)),
            ('comp-sample-component', 'Sample Component', 'draft', 'component', CAST(NULL AS VARCHAR))
        ) AS t(id, title, status, kind, owner_component_id)
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW edges AS
        SELECT * FROM (VALUES
            ('D31', 'D17', 'supersedes')
        ) AS t(source_id, target_id, edge_type)
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW decision_lineage AS
        SELECT * FROM (VALUES
            ('D17', CAST(NULL AS VARCHAR)),
            ('D31', '__D31_RATIFIED_COMMIT__')
        ) AS t(id, last_ratified_commit)
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW component_docs AS
        SELECT
            'comp-sample-component' AS id,
            'Sample Component' AS title,
            'draft' AS status,
            'Sample component body text.' AS body
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW component_context AS
        SELECT
            'comp-sample-component' AS component_id,
            'A sample component used only to host a requirement citing a decision.' AS purpose
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW component_provenance AS
        SELECT
            CAST(NULL AS VARCHAR) AS component_id,
            CAST(NULL AS VARCHAR) AS spec_bundle_hash,
            CAST(NULL AS VARCHAR) AS verification_report,
            CAST(NULL AS VARCHAR) AS license_scan,
            CAST(NULL AS VARCHAR) AS secret_scan,
            CAST(NULL AS BOOLEAN) AS provenance_hit
        WHERE FALSE
        """
    )
    con.execute(
        """
        CREATE OR REPLACE VIEW component_size AS
        SELECT
            'sample-component' AS component_id,
            CAST(5 AS BIGINT) AS word_count
        """
    )
'''


def test_citation_committed_after_supersession_is_not_reported_as_drift(tmp_path):
    repo_root = tmp_path
    (repo_root / "specs" / "decisions").mkdir(parents=True)

    run_git(repo_root, "init", "-q")

    d17_path = repo_root / "specs" / "decisions" / "D17.md"
    d17_path.write_text(
        "---\n"
        "id: D17\n"
        "title: Original approach\n"
        "status: deprecated\n"
        "owners: [lselfors]\n"
        "---\n"
        "\n"
        "The original approach, later superseded.\n"
    )
    run_git(repo_root, "add", "-A")
    git_commit(repo_root, "add D17")

    d31_path = repo_root / "specs" / "decisions" / "D31.md"
    d31_path.write_text(
        "---\n"
        "id: D31\n"
        "title: Replacement approach\n"
        "status: ratified\n"
        "owners: [lselfors]\n"
        "supersedes: [D17]\n"
        "last_ratified_commit: PENDING\n"
        "---\n"
        "\n"
        "Supersedes D17 with a new approach.\n"
    )
    run_git(repo_root, "add", "-A")
    git_commit(repo_root, "add D31, superseding D17")
    d31_ratified_commit = run_git(repo_root, "rev-parse", "HEAD")

    d31_path.write_text(
        d31_path.read_text().replace(
            "last_ratified_commit: PENDING",
            f"last_ratified_commit: {d31_ratified_commit}",
        )
    )
    run_git(repo_root, "add", "-A")
    git_commit(repo_root, "backfill D31 last_ratified_commit")

    component_dir = repo_root / "specs" / "components" / "sample-component"
    (component_dir / "requirements").mkdir(parents=True)
    (component_dir / "acceptance").mkdir(parents=True)

    (component_dir / "component.md").write_text(
        "---\n"
        "id: comp-sample-component\n"
        "title: Sample Component\n"
        "status: draft\n"
        "owners: [lselfors]\n"
        "sealed: true\n"
        "source_path: fake/sample-component\n"
        "---\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A sample component used only to host a requirement citing a decision.\n"
    )

    requirement_rel_path = "specs/components/sample-component/requirements/R-SAMPLE-001.md"
    (component_dir / "requirements" / "R-SAMPLE-001.md").write_text(
        "# R-SAMPLE-001\n"
        "\n"
        "The system MUST follow the approach chosen in D17.\n"
    )

    (component_dir / "acceptance" / "AC-SAMPLE-001.md").write_text(
        "# AC-SAMPLE-001\n"
        "\n"
        "Covers: R-SAMPLE-001\n"
        "\n"
        "```gherkin\n"
        "Given a sample precondition\n"
        "When something happens\n"
        "Then something else happens\n"
        "```\n"
    )

    run_git(repo_root, "add", "-A")
    git_commit(repo_root, "add sample-component citing D17")

    dep_dir = repo_root / "gen" / "graph-query-engine"
    dep_dir.mkdir(parents=True)
    module_source = FAKE_GRAPH_QUERY_ENGINE_MODULE.replace(
        "__D31_RATIFIED_COMMIT__", d31_ratified_commit
    )
    (dep_dir / "graph_query_engine.py").write_text(module_source)

    report = decision_drift_detector.find_decision_drift(repo_root)

    assert (repo_root / ".load_views_called").exists()

    entries = field(report, "entries", [])
    matching = [
        entry
        for entry in entries
        if field(entry, "file", "") == requirement_rel_path
    ]
    assert matching == []