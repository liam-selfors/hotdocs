# hotdocs-criterion: sha256:890d012efe154e6e231192246bee70586b90e4182c568540333585590a2e4e35
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import decision_drift_detector


FAKE_GQE_TEMPLATE = '''\
"""Fake graph-query-engine for AC-DRIFT-004: records every load_views call."""
import json
from pathlib import Path

_LOG_PATH = {log_path!r}


def load_views(con, repo_root):
    # Record the invocation FIRST, before anything that could raise.
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"call": "load_views", "repo_root": str(repo_root)}}) + "\\n")

    statements = [
        """CREATE OR REPLACE VIEW nodes AS
           SELECT CAST(NULL AS VARCHAR) AS id,
                  CAST(NULL AS VARCHAR) AS title,
                  CAST(NULL AS VARCHAR) AS status,
                  CAST(NULL AS VARCHAR) AS kind,
                  CAST(NULL AS VARCHAR) AS owner_component_id
           WHERE FALSE""",
        """CREATE OR REPLACE VIEW edges AS
           SELECT CAST(NULL AS VARCHAR) AS source_id,
                  CAST(NULL AS VARCHAR) AS target_id,
                  CAST(NULL AS VARCHAR) AS edge_type
           WHERE FALSE""",
        """CREATE OR REPLACE VIEW component_docs AS
           SELECT CAST(NULL AS VARCHAR) AS id,
                  CAST(NULL AS VARCHAR) AS title,
                  CAST(NULL AS VARCHAR) AS status,
                  CAST(NULL AS VARCHAR) AS body
           WHERE FALSE""",
        """CREATE OR REPLACE VIEW component_context AS
           SELECT CAST(NULL AS VARCHAR) AS component_id,
                  CAST(NULL AS VARCHAR) AS purpose
           WHERE FALSE""",
        """CREATE OR REPLACE VIEW component_provenance AS
           SELECT CAST(NULL AS VARCHAR) AS component_id,
                  CAST(NULL AS VARCHAR) AS spec_bundle_hash,
                  CAST(NULL AS BOOLEAN) AS provenance_hit
           WHERE FALSE""",
        """CREATE OR REPLACE VIEW component_size AS
           SELECT CAST(NULL AS VARCHAR) AS component_id,
                  CAST(NULL AS BIGINT) AS word_count
           WHERE FALSE""",
        """CREATE OR REPLACE VIEW decision_lineage AS
           SELECT CAST(NULL AS VARCHAR) AS id,
                  CAST(NULL AS VARCHAR) AS last_ratified_commit
           WHERE FALSE""",
    ]
    for stmt in statements:
        con.execute(stmt)
    return None
'''


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _git(repo_root: Path, *args: str) -> None:
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Test Author"
    env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )


def _build_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test-only term.\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: A fixture decision\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "---\n\n"
        "# D1\n\nA fixture decision used only by AC-DRIFT-004.\n",
    )
    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo\n"
        "---\n\n"
        "# Foo\n\n## Purpose\n\nA fixture component.\n\n"
        "## Rationale\n\nShaped by D1.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do the thing (D1).\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen it runs\nThen the thing happens\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write(comp_dir / "interface" / "library.md", "# Library\n\n```\nfoo() -> None\n```\n")


def _is_relative_to(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def test_ac_drift_004_graph_query_engine_resolved_relative_to_repo_root(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("git is required to construct a repo_root fixture")

    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    log_dir = (tmp_path / "logs").resolve()
    log_dir.mkdir()
    log_path = log_dir / "load_views_calls.jsonl"

    # The component under test's own code must live outside repo_root.
    own_file = Path(decision_drift_detector.__file__).resolve()
    assert not _is_relative_to(own_file, repo_root), (
        "precondition: component under test must not live under the test repo_root"
    )

    # Fake graph-query-engine, flat-module shape, under repo_root/gen/.
    fake_path = repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py"
    _write(fake_path, FAKE_GQE_TEMPLATE.format(log_path=str(log_path)))

    _build_corpus(repo_root)

    _git(repo_root, "init", "-q")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "fixture corpus")

    assert not log_path.exists()

    result = decision_drift_detector.find_decision_drift(repo_root)

    assert log_path.exists(), (
        "fake graph-query-engine under repo_root/gen/ was never called: "
        "graph-query-engine was not resolved relative to repo_root"
    )
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    records = [json.loads(ln) for ln in lines]
    load_calls = [r for r in records if r.get("call") == "load_views"]
    assert len(load_calls) == 1, (
        f"expected exactly one load_views call on the repo_root fake, got {len(load_calls)}"
    )
    assert Path(load_calls[0]["repo_root"]).resolve() == repo_root

    entries = _get(result, "entries")
    assert entries is not None
    assert isinstance(list(entries), list)