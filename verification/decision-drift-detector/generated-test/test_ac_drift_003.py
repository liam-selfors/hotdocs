# hotdocs-criterion: sha256:e714d29c9eb22e335e630f341808aacbb9052e6e58b1a0e1cd7b932da5d49091
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import decision_drift_detector


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _git(repo_root, *args):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [alice]
sealed: true
source_path: legacy/foo
depends_on: []
---

# Foo

## Purpose

Does foo things.

## Rationale

Foo's behavior follows `D17`.
"""

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — Foo MUST do the thing.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given foo
When the thing happens
Then foo does the thing
```
"""

D17_MD = """---
id: D17
title: Original decision
status: deprecated
owners: [alice]
last_ratified_commit: 0000000
---

# D17

The original decision.
"""

D31_MD = """---
id: D31
title: Superseding decision
status: ratified
owners: [alice]
supersedes: [D17]
last_ratified_commit: 0000000
---

# D31

Supersedes the original decision.
"""


FAKE_GQE_TEMPLATE = '''
from pathlib import Path

_LOG_PATH = {log_path!r}
_D17_COMMIT = {d17_commit!r}
_D31_COMMIT = {d31_commit!r}


def load_views(con, repo_root):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write("load_views " + str(repo_root) + "\\n")

    con.execute(
        "CREATE OR REPLACE VIEW nodes AS SELECT * FROM (VALUES "
        "('D17', 'Original decision', 'deprecated', 'decision', CAST(NULL AS VARCHAR)), "
        "('D31', 'Superseding decision', 'ratified', 'decision', CAST(NULL AS VARCHAR)), "
        "('comp-foo', 'Foo', 'draft', 'component', CAST(NULL AS VARCHAR)), "
        "('R-FOO-001', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR), 'requirement', 'comp-foo'), "
        "('AC-FOO-001', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR), 'acceptance', 'comp-foo')"
        ") AS t(id, title, status, kind, owner_component_id)"
    )
    con.execute(
        "CREATE OR REPLACE VIEW edges AS SELECT * FROM (VALUES "
        "('D31', 'D17', 'supersedes'), "
        "('AC-FOO-001', 'R-FOO-001', 'covers')"
        ") AS t(source_id, target_id, edge_type)"
    )
    con.execute(
        "CREATE OR REPLACE VIEW decision_lineage AS SELECT * FROM (VALUES "
        "('D17', '" + _D17_COMMIT + "'), "
        "('D31', '" + _D31_COMMIT + "')"
        ") AS t(id, last_ratified_commit)"
    )
    con.execute(
        "CREATE OR REPLACE VIEW component_docs AS SELECT * FROM (VALUES "
        "('comp-foo', 'Foo', 'draft', '')"
        ") AS t(id, title, status, body)"
    )
    con.execute(
        "CREATE OR REPLACE VIEW component_context AS SELECT * FROM (VALUES "
        "('comp-foo', 'Does foo things.')"
        ") AS t(component_id, purpose)"
    )
    con.execute(
        "CREATE OR REPLACE VIEW component_provenance AS SELECT "
        "CAST(NULL AS VARCHAR) AS component_id, "
        "CAST(NULL AS VARCHAR) AS spec_bundle_hash, "
        "CAST(NULL AS STRUCT(result VARCHAR)) AS verification_report, "
        "CAST(NULL AS STRUCT(result VARCHAR)) AS license_scan, "
        "CAST(NULL AS STRUCT(result VARCHAR)) AS secret_scan, "
        "CAST(NULL AS BOOLEAN) AS provenance_hit "
        "WHERE FALSE"
    )
    con.execute(
        "CREATE OR REPLACE VIEW component_size AS SELECT * FROM (VALUES "
        "('foo', CAST(10 AS BIGINT))"
        ") AS t(component_id, word_count)"
    )
    return None
'''


def _normalize(entry, repo_root):
    s = str(entry)
    p = Path(s)
    if p.is_absolute():
        try:
            return Path(os.path.realpath(s)).relative_to(repo_root).as_posix()
        except ValueError:
            return p.as_posix()
    return p.as_posix().lstrip("./") if s.startswith("./") else p.as_posix()


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_ac_drift_003_impact_reports_dependent_and_citing_file(tmp_path):
    repo_root = Path(os.path.realpath(str(tmp_path / "repo")))
    repo_root.mkdir(parents=True)
    log_path = Path(os.path.realpath(str(tmp_path))) / "gqe_calls.log"

    _git(repo_root, "init", "-q")

    # Commit 1: the first decision and a live spec file citing it.
    _write(repo_root / "specs" / "decisions" / "D17.md", D17_MD)
    component_dir = repo_root / "specs" / "components" / "foo"
    _write(component_dir / "component.md", COMPONENT_MD)
    _write(component_dir / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(component_dir / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "add D17 and foo citing it")
    d17_commit = _git(repo_root, "rev-parse", "HEAD")

    # Commit 2: the superseding decision, created after the citing file.
    _write(repo_root / "specs" / "decisions" / "D31.md", D31_MD)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "add D31 superseding D17")
    d31_commit = _git(repo_root, "rev-parse", "HEAD")

    # Fake graph-query-engine dependency, flat-module shape.
    fake_path = repo_root / "gen" / "graph-query-engine" / "graph_query_engine.py"
    _write(
        fake_path,
        FAKE_GQE_TEMPLATE.format(
            log_path=str(log_path),
            d17_commit=d17_commit,
            d31_commit=d31_commit,
        ),
    )

    report = decision_drift_detector.find_decision_impact(repo_root, "D17")

    assert log_path.exists(), "fake graph-query-engine load_views was never invoked"
    assert "load_views" in log_path.read_text(encoding="utf-8")

    decision_id = _field(report, "decision_id")
    assert decision_id == "D17"

    dependent = _field(report, "dependent_decisions")
    assert dependent is not None, "report has no dependent_decisions"
    dependent_ids = [str(d) for d in dependent]
    assert "D31" in dependent_ids, (
        "expected D31 (which supersedes D17) in dependent_decisions, got %r"
        % (dependent_ids,)
    )

    citing = _field(report, "citing_files")
    assert citing is not None, "report has no citing_files"
    citing_norm = [_normalize(c, repo_root) for c in citing]
    assert "specs/components/foo/component.md" in citing_norm, (
        "expected the live spec file citing D17 in citing_files, got %r"
        % (citing_norm,)
    )