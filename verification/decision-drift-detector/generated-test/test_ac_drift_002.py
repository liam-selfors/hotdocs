"""AC-DRIFT-002 — a spec file citing a superseded decision, whose own
last-touching commit is a descendant of (not an ancestor of) the
superseding decision's ratification commit, MUST NOT be reported as a
drift candidate (R-DRIFT-002).

A positive control file (citing the same superseded decision, but last
touched strictly before the superseder's ratification) is included so
an always-empty report cannot satisfy this test vacuously.
"""

import json
import os
import subprocess
from pathlib import Path

import decision_drift_detector


STALE_REL = "specs/components/foo/requirements/R-FOO-001.md"
FRESH_REL = "specs/components/foo/requirements/R-FOO-002.md"


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _git(repo_root, *args):
    env = dict(os.environ)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test Author"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"
    result = subprocess.run(
        [
            "git",
            "-c", "user.name=Test Author",
            "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false",
            "-c", "init.defaultBranch=main",
            *args,
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"git {' '.join(args)} failed: {result.stdout}\n{result.stderr}"
    )
    return result.stdout.strip()


def _write(repo_root, rel, text):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _commit_all(repo_root, message):
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", message)
    return _git(repo_root, "rev-parse", "HEAD")


def _decision_d17(status, last_ratified_commit):
    return (
        "---\n"
        "id: D17\n"
        "title: Original foo approach\n"
        f"status: {status}\n"
        "owners: [alice]\n"
        f"last_ratified_commit: {last_ratified_commit}\n"
        "---\n"
        "\n"
        "# D17 — Original foo approach\n"
        "\n"
        "Foo does X the original way.\n"
    )


def _decision_d31(last_ratified_commit):
    return (
        "---\n"
        "id: D31\n"
        "title: Revised foo approach\n"
        "status: ratified\n"
        "owners: [alice]\n"
        "supersedes: [D17]\n"
        f"last_ratified_commit: {last_ratified_commit}\n"
        "---\n"
        "\n"
        "# D31 — Revised foo approach\n"
        "\n"
        "Foo does X the revised way instead.\n"
    )


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [alice]\n"
    "depends_on: []\n"
    "sealed: true\n"
    "source_path: legacy/foo\n"
    "---\n"
    "\n"
    "# comp-foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does a small thing for testing.\n"
)


FAKE_GQE_TEMPLATE = '''
import json as _json

_LOG_PATH = {log_path!r}
_D17_COMMIT = {d17_commit!r}
_D31_COMMIT = {d31_commit!r}


def load_views(con, repo_root):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps({{"call": "load_views", "repo_root": str(repo_root)}}) + "\\n")

    con.execute(
        "CREATE OR REPLACE VIEW nodes AS "
        "SELECT * FROM (VALUES "
        "('comp-foo', 'Foo', 'draft', 'component', CAST(NULL AS VARCHAR)), "
        "('R-FOO-001', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR), 'requirement', 'comp-foo'), "
        "('R-FOO-002', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR), 'requirement', 'comp-foo'), "
        "('AC-FOO-001', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR), 'acceptance', 'comp-foo'), "
        "('AC-FOO-002', CAST(NULL AS VARCHAR), CAST(NULL AS VARCHAR), 'acceptance', 'comp-foo'), "
        "('D17', 'Original foo approach', 'deprecated', 'decision', CAST(NULL AS VARCHAR)), "
        "('D31', 'Revised foo approach', 'ratified', 'decision', CAST(NULL AS VARCHAR))"
        ") AS t(id, title, status, kind, owner_component_id)"
    )

    con.execute(
        "CREATE OR REPLACE VIEW edges AS "
        "SELECT * FROM (VALUES "
        "('AC-FOO-001', 'R-FOO-001', 'covers'), "
        "('AC-FOO-002', 'R-FOO-002', 'covers'), "
        "('D31', 'D17', 'supersedes')"
        ") AS t(source_id, target_id, edge_type)"
    )

    con.execute(
        "CREATE OR REPLACE VIEW decision_lineage AS "
        "SELECT * FROM (VALUES "
        "('D17', '" + _D17_COMMIT + "'), "
        "('D31', '" + _D31_COMMIT + "')"
        ") AS t(id, last_ratified_commit)"
    )

    con.execute(
        "CREATE OR REPLACE VIEW component_docs AS "
        "SELECT * FROM (VALUES "
        "('comp-foo', 'Foo', 'draft', 'Foo does a small thing for testing.')"
        ") AS t(id, title, status, body)"
    )

    con.execute(
        "CREATE OR REPLACE VIEW component_context AS "
        "SELECT * FROM (VALUES "
        "('comp-foo', 'Foo does a small thing for testing.')"
        ") AS t(component_id, purpose)"
    )

    con.execute(
        "CREATE OR REPLACE VIEW component_size AS "
        "SELECT * FROM (VALUES "
        "('foo', CAST(6 AS BIGINT))"
        ") AS t(component_id, word_count)"
    )

    con.execute(
        "CREATE OR REPLACE VIEW component_provenance AS "
        "SELECT "
        "CAST(NULL AS VARCHAR) AS component_id, "
        "CAST(NULL AS VARCHAR) AS spec_bundle_hash, "
        "CAST(NULL AS STRUCT(result VARCHAR)) AS verification_report, "
        "CAST(NULL AS STRUCT(result VARCHAR)) AS license_scan, "
        "CAST(NULL AS STRUCT(result VARCHAR)) AS secret_scan, "
        "CAST(NULL AS BOOLEAN) AS provenance_hit "
        "WHERE FALSE"
    )

    return None
'''


def _path_matches(entry_file, rel):
    if entry_file is None:
        return False
    norm = str(entry_file).replace("\\", "/")
    return norm == rel or norm.endswith("/" + rel)


def _build_fixture(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "gqe_calls.log"

    _git(repo_root, "init", "-q")
    # Keep the fake dependency out of git's view entirely.
    exclude = repo_root / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with open(exclude, "a", encoding="utf-8") as fh:
        fh.write("\ngen/\n")

    # c1: D17 ratified; component + a requirement citing D17 (stale control).
    _write(repo_root, "specs/decisions/D17.md",
           _decision_d17("ratified", "0000000000000000000000000000000000000000"))
    _write(repo_root, "specs/components/foo/component.md", COMPONENT_MD)
    _write(repo_root, STALE_REL,
           "# R-FOO-001\n\n**R-FOO-001** — Foo MUST do X the original way, per D17.\n")
    _write(repo_root, "specs/components/foo/acceptance/AC-FOO-001.md",
           "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
           "Given foo\nWhen run\nThen X happens\n")
    c1 = _commit_all(repo_root, "D17 ratified; R-FOO-001 written")

    # c2: D31 ratified, superseding D17; D17 deprecated. This is D31's ratification.
    _write(repo_root, "specs/decisions/D17.md", _decision_d17("deprecated", c1))
    _write(repo_root, "specs/decisions/D31.md",
           _decision_d31("0000000000000000000000000000000000000000"))
    c2 = _commit_all(repo_root, "D31 ratified, supersedes D17")

    # c3: record D31's real ratification commit in its own frontmatter.
    _write(repo_root, "specs/decisions/D31.md", _decision_d31(c2))
    _commit_all(repo_root, "record D31 last_ratified_commit")

    # c4: a spec file citing D17, written after the supersession.
    _write(repo_root, FRESH_REL,
           "# R-FOO-002\n\n**R-FOO-002** — Foo MUST log X, consistent with D17.\n")
    _write(repo_root, "specs/components/foo/acceptance/AC-FOO-002.md",
           "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: generated-test\n\n"
           "Given foo\nWhen run\nThen X is logged\n")
    c4 = _commit_all(repo_root, "R-FOO-002 written after D31")

    # Sanity: fixture ancestry is what the criterion describes.
    def _is_ancestor(a, b):
        return subprocess.run(
            ["git", "merge-base", "--is-ancestor", a, b],
            cwd=str(repo_root), capture_output=True,
        ).returncode == 0

    assert _is_ancestor(c2, c4), "fresh file's commit must descend from D31's ratification"
    assert not _is_ancestor(c4, c2), "fresh file's commit must not predate D31's ratification"
    assert _is_ancestor(c1, c2), "control file's commit must predate D31's ratification"

    # Fake graph-query-engine dependency, flat-module shape.
    fake_dir = repo_root / "gen" / "graph-query-engine"
    fake_dir.mkdir(parents=True, exist_ok=True)
    (fake_dir / "graph_query_engine.py").write_text(
        FAKE_GQE_TEMPLATE.format(
            log_path=str(log_path), d17_commit=c1, d31_commit=c2
        ),
        encoding="utf-8",
    )

    return repo_root, log_path, c1, c2, c4


def test_ac_drift_002_file_written_after_supersession_is_not_stale(tmp_path):
    repo_root, log_path, c1, c2, c4 = _build_fixture(tmp_path)

    report = decision_drift_detector.find_decision_drift(Path(repo_root))

    # Confirm the faked dependency actually ran.
    assert log_path.exists(), "fake graph-query-engine load_views was never invoked"
    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(calls) >= 1, "fake graph-query-engine load_views was never invoked"

    entries = _get(report, "entries")
    assert entries is not None, "DriftReport has no 'entries' field"
    entries = list(entries)

    # Core assertion: the file written after D31's ratification is not reported.
    fresh_hits = [e for e in entries if _path_matches(_get(e, "file"), FRESH_REL)]
    assert fresh_hits == [], (
        f"file last touched after D31's ratification was wrongly reported as drift: {fresh_hits!r}"
    )

    # Positive control: the file last touched before D31's ratification IS reported,
    # so the empty result above is not a vacuous always-empty report.
    stale_hits = [
        e for e in entries
        if _path_matches(_get(e, "file"), STALE_REL)
        and str(_get(e, "cited_decision")) == "D17"
    ]
    assert len(stale_hits) == 1, (
        f"expected exactly one drift entry for the pre-supersession control file, got {entries!r}"
    )
    assert str(_get(stale_hits[0], "superseded_by")) == "D31"