import io
import json
import os
import shutil
import subprocess
import sys
import contextlib
from pathlib import Path

import pytest

import decision_drift_detector


GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(GIT is None, reason="git executable not available")


FAKE_GQE_SOURCE = '''
from pathlib import Path


def load_views(con, repo_root):
    """Fake graph-query-engine load_views(con, repo_root) -> None.

    Creates (or replaces) all seven documented views on `con`, scoped to a
    tiny fixture corpus containing exactly one draft decision D1 and no
    supersedes/builds_on edges -- i.e. a corpus with no drift.
    """
    statements = [
        """
        CREATE OR REPLACE VIEW nodes AS
        SELECT * FROM (
            VALUES ('D1', 'Fixture decision', 'draft', 'decision', CAST(NULL AS VARCHAR))
        ) AS t(id, title, status, kind, owner_component_id)
        """,
        """
        CREATE OR REPLACE VIEW edges AS
        SELECT
            CAST(NULL AS VARCHAR) AS source_id,
            CAST(NULL AS VARCHAR) AS target_id,
            CAST(NULL AS VARCHAR) AS edge_type
        WHERE 1 = 0
        """,
        """
        CREATE OR REPLACE VIEW component_docs AS
        SELECT
            CAST(NULL AS VARCHAR) AS id,
            CAST(NULL AS VARCHAR) AS title,
            CAST(NULL AS VARCHAR) AS status,
            CAST(NULL AS VARCHAR) AS body
        WHERE 1 = 0
        """,
        """
        CREATE OR REPLACE VIEW component_context AS
        SELECT
            CAST(NULL AS VARCHAR) AS component_id,
            CAST(NULL AS VARCHAR) AS purpose
        WHERE 1 = 0
        """,
        """
        CREATE OR REPLACE VIEW component_provenance AS
        SELECT
            CAST(NULL AS VARCHAR) AS component_id,
            CAST(NULL AS VARCHAR) AS spec_bundle_hash,
            CAST(NULL AS STRUCT(result VARCHAR)) AS verification_report,
            CAST(NULL AS STRUCT(result VARCHAR)) AS license_scan,
            CAST(NULL AS STRUCT(result VARCHAR)) AS secret_scan,
            CAST(NULL AS BOOLEAN) AS provenance_hit
        WHERE 1 = 0
        """,
        """
        CREATE OR REPLACE VIEW component_size AS
        SELECT
            CAST(NULL AS VARCHAR) AS component_id,
            CAST(NULL AS BIGINT) AS word_count
        WHERE 1 = 0
        """,
        """
        CREATE OR REPLACE VIEW decision_lineage AS
        SELECT * FROM (
            VALUES ('D1', CAST(NULL AS VARCHAR))
        ) AS t(id, last_ratified_commit)
        """,
    ]
    for statement in statements:
        con.execute(statement)
    return None
'''


DECISION_D1 = """---
id: D1
title: Fixture decision
status: draft
owners: [test-owner]
---

# D1 — Fixture decision

A synthetic draft decision used only as a test fixture. Nothing
supersedes it and nothing builds on it.
"""


def _git(repo, *args):
    env = dict(os.environ)
    env.setdefault("GIT_CONFIG_NOSYSTEM", "1")
    return subprocess.run(
        [
            GIT,
            "-c", "user.name=Test Fixture",
            "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false",
            "-c", "init.defaultBranch=main",
            *args,
        ],
        cwd=str(repo),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _make_clean_repo(base: Path) -> Path:
    repo = base / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")

    decisions = repo / "specs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "D1.md").write_text(DECISION_D1, encoding="utf-8")

    gqe_dir = repo / "gen" / "graph-query-engine"
    gqe_dir.mkdir(parents=True)
    (gqe_dir / "graph_query_engine.py").write_text(FAKE_GQE_SOURCE, encoding="utf-8")

    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "fixture corpus")
    return repo


@pytest.fixture
def clean_repo(tmp_path):
    return _make_clean_repo(tmp_path)


def _run_main(argv):
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = decision_drift_detector.main(argv)
        except SystemExit as exc:
            code = exc.code
    if code is None:
        code = 0
    return code, out.getvalue(), err.getvalue()


def _parse_json(text):
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except ValueError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        assert start != -1 and end != -1 and end > start, (
            f"stdout does not contain a JSON object: {text!r}"
        )
        return json.loads(stripped[start:end + 1])


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def test_decision_drift_json_clean_repo_returns_0_with_empty_entries(clean_repo):
    code, out, err = _run_main(
        ["decision-drift", f"--repo-root={clean_repo}", "--format=json"]
    )
    assert code == 0, f"expected exit 0, got {code!r}; stderr={err!r}"
    report = _parse_json(out)
    entries = _field(report, "entries")
    assert isinstance(entries, list), f"report has no entries list: {report!r}"
    assert entries == []


def test_decision_impact_text_returns_0_and_prints_human_readable(clean_repo):
    code, out, err = _run_main(
        ["decision-impact", "D1", f"--repo-root={clean_repo}"]
    )
    assert code == 0, f"expected exit 0, got {code!r}; stderr={err!r}"
    assert out.strip(), "expected a non-empty human-readable report on stdout"
    parsed_as_json_object = False
    try:
        parsed_as_json_object = isinstance(json.loads(out.strip()), dict)
    except ValueError:
        parsed_as_json_object = False
    assert not parsed_as_json_object, (
        f"default format should be human-readable text, not JSON: {out!r}"
    )


def test_decision_impact_missing_decision_id_returns_2(clean_repo):
    code, _out, _err = _run_main(
        ["decision-impact", f"--repo-root={clean_repo}"]
    )
    assert code == 2


def test_decision_drift_not_a_git_repository_returns_2(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    not_repo = tmp_path / "notrepo"
    not_repo.mkdir()
    (not_repo / "README.md").write_text("not a git repository\n", encoding="utf-8")
    code, _out, _err = _run_main(
        ["decision-drift", f"--repo-root={not_repo}"]
    )
    assert code == 2


def test_decision_drift_defaults_repo_root_to_cwd_git_root(clean_repo, monkeypatch):
    monkeypatch.chdir(clean_repo)
    code, _out, err = _run_main(["decision-drift"])
    assert code == 0, f"expected exit 0, got {code!r}; stderr={err!r}"


def test_decision_drift_bogus_format_returns_2(clean_repo):
    code, _out, _err = _run_main(
        ["decision-drift", f"--repo-root={clean_repo}", "--format=bogus"]
    )
    assert code == 2