# hotdocs-criterion: sha256:0ba78304d73d799533b8d8a9daf4abe3cb287db8f452d95d2009794ee2ffa63e
"""AC-DRIFT-002: a spec file citing a superseded decision, but last touched
after the superseding decision's ratification, is not reported as drift."""

import subprocess
from pathlib import Path

import decision_drift_detector


GIT_CFG = [
    "-c", "user.name=t",
    "-c", "user.email=t@t",
    "-c", "commit.gpgsign=false",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo_root, *args):
    result = subprocess.run(
        ["git"] + GIT_CFG + list(args),
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def commit(repo_root, message):
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", message)


def short_head(repo_root):
    return git(repo_root, "rev-parse", "--short", "HEAD")


def full_head(repo_root):
    return git(repo_root, "rev-parse", "HEAD")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def decision_text(decision_id, title, status, last_ratified_commit=None, supersedes=None):
    lines = [
        "---",
        "id: " + decision_id,
        "title: " + title,
        "status: " + status,
        "owners: [pipeline-team]",
    ]
    if supersedes is not None:
        lines.append("supersedes: " + supersedes)
    if last_ratified_commit is not None:
        lines.append("last_ratified_commit: " + last_ratified_commit)
    lines.append("---")
    lines.append("")
    lines.append("# " + decision_id)
    lines.append("")
    lines.append(title + ".")
    lines.append("")
    return "\n".join(lines)


def component_text():
    return "\n".join([
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
        "sealed: true",
        "source_path: legacy/foo/",
        "---",
        "",
        "# Foo",
        "",
        "## Purpose",
        "",
        "A fixture component.",
        "",
    ])


def requirement_text(req_id, cited):
    return "\n".join([
        "# " + req_id,
        "",
        "**" + req_id + "** - MUST behave as decided in " + cited + ".",
        "",
    ])


def acceptance_text(ac_id, req_id):
    return "\n".join([
        "# " + ac_id,
        "",
        "Covers: " + req_id,
        "Kind: generated-test",
        "",
        "Given a thing",
        "When it runs",
        "Then it works",
        "",
    ])


def matches(entry_file, rel_path):
    normalized = Path(str(entry_file)).as_posix()
    return normalized == rel_path or normalized.endswith("/" + rel_path)


def test_file_touched_after_supersession_is_not_reported(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init", "-q")

    decisions = repo_root / "specs" / "decisions"
    comp = repo_root / "specs" / "components" / "foo"

    control_rel = "specs/components/foo/requirements/R-FOO-001.md"
    target_rel = "specs/components/foo/requirements/R-FOO-002.md"

    # Commit A: D17 ratified, plus a control file citing D17 written
    # BEFORE the supersession (this one is a genuine drift candidate).
    write(decisions / "D17.md", decision_text("D17", "Seventeenth decision", "ratified", "0000000"))
    write(comp / "component.md", component_text())
    write(repo_root / control_rel, requirement_text("R-FOO-001", "D17"))
    write(comp / "acceptance" / "AC-FOO-001.md", acceptance_text("AC-FOO-001", "R-FOO-001"))
    commit(repo_root, "ratify D17")
    d17_ratified = short_head(repo_root)
    write(decisions / "D17.md", decision_text("D17", "Seventeenth decision", "ratified", d17_ratified))
    commit(repo_root, "record D17 commit")

    # Commit C: D17 deprecated, superseded by D31 (ratified).
    write(decisions / "D17.md", decision_text("D17", "Seventeenth decision", "deprecated", d17_ratified))
    write(decisions / "D31.md", decision_text("D31", "Thirty-first decision", "ratified", "0000000", supersedes="D17"))
    commit(repo_root, "ratify D31 superseding D17")
    d31_ratified = short_head(repo_root)
    write(decisions / "D31.md", decision_text("D31", "Thirty-first decision", "ratified", d31_ratified, supersedes="D17"))
    commit(repo_root, "record D31 commit")

    # Commit E: the target file citing D17, written after D31's ratification.
    write(repo_root / target_rel, requirement_text("R-FOO-002", "D17"))
    write(comp / "acceptance" / "AC-FOO-002.md", acceptance_text("AC-FOO-002", "R-FOO-002"))
    commit(repo_root, "add spec citing D17 after supersession")

    # Sanity: the target's last-touch commit is a descendant (not an
    # ancestor) of D31's ratification.
    target_commit = git(repo_root, "log", "-1", "--format=%H", "--", target_rel)
    assert target_commit == full_head(repo_root)
    rc = subprocess.run(
        ["git"] + GIT_CFG + ["merge-base", "--is-ancestor", target_commit, d31_ratified],
        cwd=str(repo_root),
        capture_output=True,
    ).returncode
    assert rc != 0

    report = decision_drift_detector.find_decision_drift(repo_root)
    entries = list(field(report, "entries"))

    # Then: no entry for the file written after the supersession.
    target_entries = [e for e in entries if matches(field(e, "file"), target_rel)]
    assert target_entries == [], target_entries

    # Control: the fixture really exercises the ancestry check -- the file
    # last touched before D31's ratification IS reported.
    control_entries = [
        e for e in entries
        if matches(field(e, "file"), control_rel)
        and field(e, "cited_decision") == "D17"
        and field(e, "superseded_by") == "D31"
    ]
    assert len(control_entries) == 1, entries