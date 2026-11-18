# hotdocs-criterion: sha256:035e000e3f0e137280446569e559568c30a81e38f3dd888dbf97d2263ffb396c
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import decision_drift_detector


REQ_REL = "specs/components/foo/requirements/R-FOO-001.md"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is required")


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _git_env(date=None):
    env = dict(os.environ)
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"):
        env.pop(k, None)
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test Author"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    if date is not None:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    return env


def _git(repo, *args, date=None):
    res = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "user.name=Test Author",
         "-c", "user.email=test@example.com", *args],
        cwd=str(repo),
        env=_git_env(date),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, "git %r failed: %s %s" % (args, res.stdout, res.stderr)
    return res.stdout.strip()


def _commit(repo, message, day):
    date = "2024-01-%02dT12:00:00 +0000" % day
    _git(repo, "add", "-A", "specs")
    _git(repo, "commit", "-q", "-m", message, date=date)
    return _git(repo, "rev-parse", "HEAD")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _norm_file(value, repo_root):
    if value is None:
        return None
    p = Path(str(value))
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(Path(repo_root).resolve())
        except (ValueError, OSError):
            pass
    return str(p).replace("\\", "/").lstrip("./") if str(p).startswith("./") else str(p).replace("\\", "/")


# ---------------------------------------------------------------------------
# Fixture corpus
# ---------------------------------------------------------------------------

COMPONENT_MD = """---
id: comp-foo
title: Foo
status: ratified
owners: [alice]
sealed: true
source_path: legacy/foo
last_ratified_commit: 0000000
---

# Foo

## Purpose

Does foo things for the synthetic fixture.
"""

REQ_MD = """# R-FOO-001

**R-FOO-001** — MUST do the thing exactly as decided in D17.
"""

AC_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given a foo
When the thing runs
Then the thing is done
```
"""


def _decision_md(did, title, status, supersedes=None):
    lines = [
        "---",
        "id: %s" % did,
        "title: %s" % title,
        "status: %s" % status,
        "owners: [alice]",
        "last_ratified_commit: 0000000",
    ]
    if supersedes is not None:
        lines.append("supersedes: %s" % supersedes)
    lines.append("---")
    lines.append("")
    lines.append("# %s — %s" % (did, title))
    lines.append("")
    lines.append("Decision body text.")
    lines.append("")
    return "\n".join(lines)


def _base_corpus(repo):
    _write(repo / "specs/components/foo/component.md", COMPONENT_MD)
    _write(repo / REQ_REL, REQ_MD)
    _write(repo / "specs/components/foo/acceptance/AC-FOO-001.md", AC_MD)
    _write(repo / "specs/decisions/D17.md", _decision_md("D17", "Original choice", "ratified"))


# ---------------------------------------------------------------------------
# Fake graph-query-engine (flat module under <repo_root>/gen/graph-query-engine/)
# ---------------------------------------------------------------------------

_FAKE_BODY = r'''

def _lit(value, typ):
    if value is None:
        return "CAST(NULL AS " + typ + ")"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return "CAST(" + str(value) + " AS " + typ + ")"
    return "CAST('" + str(value).replace("'", "''") + "' AS " + typ + ")"


def _view(con, name, cols, rows):
    head = (
        "SELECT "
        + ", ".join(_lit(None, t) + ' AS "' + c + '"' for c, t in cols)
        + " FROM (SELECT 1) AS _empty WHERE FALSE"
    )
    parts = [head]
    for row in rows:
        parts.append(
            "SELECT "
            + ", ".join(_lit(v, t) + ' AS "' + c + '"' for (c, t), v in zip(cols, row))
        )
    con.execute('CREATE OR REPLACE VIEW "' + name + '" AS ' + " UNION ALL ".join(parts))


def load_views(con, repo_root):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"repo_root": str(repo_root)}) + "\n")
    _view(con, "nodes",
          [("id", "VARCHAR"), ("title", "VARCHAR"), ("status", "VARCHAR"),
           ("kind", "VARCHAR"), ("owner_component_id", "VARCHAR")],
          _DATA["nodes"])
    _view(con, "edges",
          [("source_id", "VARCHAR"), ("target_id", "VARCHAR"), ("edge_type", "VARCHAR")],
          _DATA["edges"])
    _view(con, "component_docs",
          [("id", "VARCHAR"), ("title", "VARCHAR"), ("status", "VARCHAR"), ("body", "VARCHAR")],
          _DATA["component_docs"])
    _view(con, "component_context",
          [("component_id", "VARCHAR"), ("purpose", "VARCHAR")],
          _DATA["component_context"])
    _view(con, "component_provenance",
          [("component_id", "VARCHAR"), ("spec_bundle_hash", "VARCHAR"),
           ("verification_report", "STRUCT(passed BOOLEAN)"),
           ("license_scan", "STRUCT(passed BOOLEAN)"),
           ("secret_scan", "STRUCT(passed BOOLEAN)"),
           ("provenance_hit", "BOOLEAN")],
          _DATA["component_provenance"])
    _view(con, "component_size",
          [("component_id", "VARCHAR"), ("word_count", "BIGINT")],
          _DATA["component_size"])
    _view(con, "decision_lineage",
          [("id", "VARCHAR"), ("last_ratified_commit", "VARCHAR")],
          _DATA["decision_lineage"])
'''


def _install_fake_gqe(repo, log_path, decisions, edges, lineage):
    nodes = [
        ["comp-foo", "Foo", "ratified", "component", None],
        ["R-FOO-001", None, None, "requirement", "comp-foo"],
        ["AC-FOO-001", None, None, "acceptance", "comp-foo"],
    ]
    for did, title, status in decisions:
        nodes.append([did, title, status, "decision", None])
    all_edges = [["AC-FOO-001", "R-FOO-001", "covers"]] + [list(e) for e in edges]
    data = {
        "nodes": nodes,
        "edges": all_edges,
        "component_docs": [["comp-foo", "Foo", "ratified", COMPONENT_MD]],
        "component_context": [["comp-foo", "Does foo things for the synthetic fixture."]],
        "component_provenance": [],
        "component_size": [["foo", len(COMPONENT_MD.split())]],
        "decision_lineage": [list(r) for r in lineage],
    }
    source = (
        "import json\n\n"
        "_DATA = json.loads(" + repr(json.dumps(data)) + ")\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        + _FAKE_BODY
    )
    fake = repo / "gen" / "graph-query-engine" / "graph_query_engine.py"
    _write(fake, source)
    return fake


def _entries(report):
    entries = _get(report, "entries")
    assert entries is not None, "DriftReport has no 'entries'"
    return list(entries)


def _entries_for_file(entries, repo):
    out = []
    for e in entries:
        f = _norm_file(_get(e, "file"), repo)
        if f == REQ_REL:
            out.append(e)
    return out


def _assert_fake_used(log_path):
    assert log_path.exists(), "fake graph_query_engine.load_views was never called"
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) >= 1


# ---------------------------------------------------------------------------
# Scenario 1: D17 superseded by D31 in a later commit
# ---------------------------------------------------------------------------

def test_single_superseder_produces_one_entry(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")

    _base_corpus(repo)
    c1 = _commit(repo, "initial corpus citing D17", 1)

    _write(repo / "specs/decisions/D17.md", _decision_md("D17", "Original choice", "deprecated"))
    _write(repo / "specs/decisions/D31.md",
           _decision_md("D31", "Replacement choice", "ratified", supersedes="D17"))
    c2 = _commit(repo, "ratify D31 superseding D17", 2)

    log_path = tmp_path / "gqe_calls.log"
    _install_fake_gqe(
        repo,
        log_path,
        decisions=[("D17", "Original choice", "deprecated"),
                   ("D31", "Replacement choice", "ratified")],
        edges=[("D31", "D17", "supersedes")],
        lineage=[("D17", c1), ("D31", c2)],
    )

    report = decision_drift_detector.find_decision_drift(repo)

    _assert_fake_used(log_path)

    entries = _entries(report)
    for_file = _entries_for_file(entries, repo)
    assert len(for_file) == 1, "expected exactly one entry for %s, got %r" % (REQ_REL, entries)

    entry = for_file[0]
    assert _get(entry, "cited_decision") == "D17"
    assert _get(entry, "superseded_by") == "D31"


# ---------------------------------------------------------------------------
# Scenario 2: D17 superseded by D31 then D32 (D32's commit descends from D31's)
# ---------------------------------------------------------------------------

def test_latest_ratified_superseder_wins(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")

    _base_corpus(repo)
    c1 = _commit(repo, "initial corpus citing D17", 1)

    _write(repo / "specs/decisions/D17.md", _decision_md("D17", "Original choice", "deprecated"))
    _write(repo / "specs/decisions/D31.md",
           _decision_md("D31", "First replacement", "ratified", supersedes="D17"))
    c2 = _commit(repo, "ratify D31 superseding D17", 2)

    _write(repo / "specs/decisions/D32.md",
           _decision_md("D32", "Second replacement", "ratified", supersedes="D17"))
    c3 = _commit(repo, "ratify D32 superseding D17", 3)

    # Sanity: D32's ratification commit is a descendant of D31's.
    res = subprocess.run(
        ["git", "merge-base", "--is-ancestor", c2, c3],
        cwd=str(repo), env=_git_env(), capture_output=True, text=True,
    )
    assert res.returncode == 0

    log_path = tmp_path / "gqe_calls.log"
    _install_fake_gqe(
        repo,
        log_path,
        decisions=[("D17", "Original choice", "deprecated"),
                   ("D31", "First replacement", "ratified"),
                   ("D32", "Second replacement", "ratified")],
        edges=[("D31", "D17", "supersedes"), ("D32", "D17", "supersedes")],
        lineage=[("D17", c1), ("D31", c2), ("D32", c3)],
    )

    report = decision_drift_detector.find_decision_drift(repo)

    _assert_fake_used(log_path)

    entries = _entries(report)
    citing_d17 = [
        e for e in _entries_for_file(entries, repo)
        if _get(e, "cited_decision") == "D17"
    ]
    assert len(citing_d17) == 1, "expected exactly one D17 entry for %s, got %r" % (REQ_REL, entries)

    entry = citing_d17[0]
    assert _get(entry, "superseded_by") == "D32"
    assert _get(entry, "superseded_by") != "D31"