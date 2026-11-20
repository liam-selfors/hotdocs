# hotdocs-criterion: sha256:faaf56070f69280604ee25114011b0d9cb2b04705facb84607fd1fb4593386db
import subprocess
from pathlib import Path

import decision_drift_detector


GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo_root, *args):
    result = subprocess.run(
        GIT + list(args),
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def decision_text(did, title, status, last_ratified_commit=None, supersedes=None):
    lines = [
        "---",
        "id: " + did,
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
    lines.append("# " + did)
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
        "Foo does foo things.",
        "",
    ])


def requirement_text(rid):
    return "**" + rid + "** — MUST do the foo thing as decided in `D17`.\n"


def acceptance_text(acid, rid):
    return "\n".join([
        "# " + acid,
        "",
        "Covers: " + rid,
        "Kind: generated-test",
        "",
        "```gherkin",
        "Given foo",
        "When foo runs",
        "Then foo happens",
        "```",
        "",
    ])


def normalize(path_value, repo_root):
    p = Path(str(path_value))
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(Path(repo_root).resolve())
        except ValueError:
            pass
    return p.as_posix()


def test_file_written_after_supersession_is_not_reported(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init", "-q")

    decisions = repo_root / "specs" / "decisions"
    comp = repo_root / "specs" / "components" / "foo"

    early_rel = "specs/components/foo/requirements/R-FOO-001.md"
    late_rel = "specs/components/foo/requirements/R-FOO-002.md"

    # Commit 1: D17 ratified, plus an early spec file citing D17 (control).
    write(decisions / "D17.md", decision_text("D17", "Original decision", "ratified", "0000000"))
    write(comp / "component.md", component_text())
    write(repo_root / early_rel, requirement_text("R-FOO-001"))
    write(comp / "acceptance" / "AC-FOO-001.md", acceptance_text("AC-FOO-001", "R-FOO-001"))
    commit(repo_root, "ratify D17")
    d17_commit = short_head(repo_root)
    write(decisions / "D17.md", decision_text("D17", "Original decision", "ratified", d17_commit))
    commit(repo_root, "record D17 commit")

    # Commit: D31 ratified, superseding D17; D17 deprecated.
    write(decisions / "D17.md", decision_text("D17", "Original decision", "deprecated", d17_commit))
    write(
        decisions / "D31.md",
        decision_text("D31", "Superseding decision", "ratified", "0000000", supersedes="D17"),
    )
    commit(repo_root, "ratify D31 superseding D17")
    d31_commit = short_head(repo_root)
    write(
        decisions / "D31.md",
        decision_text("D31", "Superseding decision", "ratified", d31_commit, supersedes="D17"),
    )
    commit(repo_root, "record D31 commit")

    # Later commit: a spec file citing D17, written after the supersession.
    write(repo_root / late_rel, requirement_text("R-FOO-002"))
    write(comp / "acceptance" / "AC-FOO-002.md", acceptance_text("AC-FOO-002", "R-FOO-002"))
    commit(repo_root, "add late citation of D17")

    late_commit = git(repo_root, "log", "-1", "--format=%H", "--", late_rel)
    d31_full = git(repo_root, "rev-parse", d31_commit)
    # Sanity: late file's commit is a descendant of D31's ratification, not an ancestor.
    assert subprocess.run(
        GIT + ["merge-base", "--is-ancestor", late_commit, d31_full],
        cwd=str(repo_root),
        capture_output=True,
    ).returncode != 0

    report = decision_drift_detector.find_decision_drift(repo_root)
    entries = list(field(report, "entries"))
    files = [normalize(field(e, "file"), repo_root) for e in entries]

    # Control: the early file predates D31's ratification and is reported,
    # proving the detector actually sees this corpus's citations.
    assert early_rel in files, files

    # The criterion: the file written after the supersession is not stale.
    assert late_rel not in files, files
    for e in entries:
        if normalize(field(e, "file"), repo_root) == late_rel:
            raise AssertionError("late file reported as drift: " + repr(e))