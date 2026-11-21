# hotdocs-criterion: sha256:fda7a6bbf43f3c555881506a72512435f4843e2c58bfb3360fc7285e5a56e793
import subprocess
from pathlib import Path

import decision_drift_detector
import spec_scaffolder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo_root, *args):
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def commit_all(repo_root, message):
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", message)
    return git(repo_root, "rev-parse", "HEAD")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def frontmatter_lines(path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---"
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        out.append(line.strip())
    return out


def test_cs_decision_integrity_001(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init", "-q")
    git(repo_root, "config", "user.name", "Test User")
    git(repo_root, "config", "user.email", "test@example.invalid")
    git(repo_root, "config", "commit.gpgsign", "false")

    (repo_root / "specs" / "decisions").mkdir(parents=True)
    write(repo_root / "README.md", "fixture repo\n")
    commit_all(repo_root, "initial")

    # The earlier decision: created, ratified, committed, commit recorded.
    earlier_path = spec_scaffolder.new_decision(
        repo_root, "Earlier decision", owners=["team-a"]
    )
    earlier_id = Path(earlier_path).stem
    spec_scaffolder.ratify(repo_root, earlier_id)
    commit_all(repo_root, "ratify " + earlier_id)
    spec_scaffolder.record_commit(repo_root, earlier_id)
    commit_all(repo_root, "record commit for " + earlier_id)

    # A live spec file citing the earlier decision, committed before the
    # superseding decision exists or is ratified.
    comp_dir = repo_root / "specs" / "components" / "foo"
    write(
        comp_dir / "component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: ratified\n"
        + "last_ratified_commit: 0000000\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "---\n\n"
        + "# Foo\n\n"
        + "A small fixture component.\n",
    )
    citing_rel = "specs/components/foo/requirements/R-FOO-001.md"
    write(
        repo_root / citing_rel,
        "# R-FOO-001: Foo does the thing\n\n"
        + "Foo does the thing, following `" + earlier_id + "`.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        + "Covers: R-FOO-001\n\n"
        + "Given foo, when it runs, then it does the thing.\n",
    )
    file_commit = commit_all(repo_root, "add foo citing " + earlier_id)

    # The later, superseding decision: created, ratified, committed after.
    later_path = spec_scaffolder.new_decision(
        repo_root, "Later decision", owners=["team-a"], supersedes=earlier_id
    )
    later_id = Path(later_path).stem
    assert later_id != earlier_id
    later_abs = Path(later_path)
    if not later_abs.is_absolute():
        later_abs = repo_root / later_abs
    lines = frontmatter_lines(later_abs)
    assert ("supersedes: " + earlier_id) in lines
    assert not any(l.startswith("supersedes: [") for l in lines)

    spec_scaffolder.ratify(repo_root, later_id)
    ratify_commit = commit_all(repo_root, "ratify " + later_id)
    spec_scaffolder.record_commit(repo_root, later_id)
    commit_all(repo_root, "record commit for " + later_id)

    # Sanity: the citing file's last commit is a strict ancestor of the
    # superseding decision's ratification commit.
    assert file_commit != ratify_commit
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", file_commit, ratify_commit],
        cwd=str(repo_root),
        check=True,
    )

    report = decision_drift_detector.find_decision_drift(repo_root)
    entries = list(field(report, "entries"))

    def matches(entry):
        file_value = Path(str(field(entry, "file")))
        if file_value.is_absolute():
            try:
                file_value = file_value.resolve().relative_to(repo_root.resolve())
            except ValueError:
                return False
        return (
            file_value.as_posix() == citing_rel
            and str(field(entry, "cited_decision")) == earlier_id
        )

    assert any(matches(e) for e in entries), (
        "expected drift entry for "
        + repr((citing_rel, earlier_id))
        + " in "
        + repr(entries)
    )