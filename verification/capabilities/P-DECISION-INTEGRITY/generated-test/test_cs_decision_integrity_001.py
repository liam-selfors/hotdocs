# hotdocs-criterion: sha256:6204ed95256d912b0ed8f3b68d2f665520fa34d9c91a70a1bca7eae2e2e3852e
import os
import subprocess
from pathlib import Path

import decision_drift_detector
import spec_scaffolder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo_root, *args):
    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = "Test"
    env["GIT_AUTHOR_EMAIL"] = "test@example.invalid"
    env["GIT_COMMITTER_NAME"] = "Test"
    env["GIT_COMMITTER_EMAIL"] = "test@example.invalid"
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main"] + list(args),
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def commit_all(repo_root, message):
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", message)
    return git(repo_root, "rev-parse", "HEAD")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def frontmatter_lines(text):
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---"
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        out.append(line)
    return out


def test_superseded_citation_in_stale_file_appears_in_drift_report(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    git(repo_root, "init", "-q")

    # The earlier decision, ratified and committed.
    d1_path = Path(spec_scaffolder.new_decision(repo_root, "Original approach", owners=["team-a"]))
    d1 = d1_path.stem
    spec_scaffolder.ratify(repo_root, d1)
    commit_all(repo_root, "Ratify " + d1)
    spec_scaffolder.record_commit(repo_root, d1)
    commit_all(repo_root, "Record commit for " + d1)

    # A live spec file citing the earlier decision, last touched now.
    comp_dir = repo_root / "specs" / "components" / "foo"
    write(
        comp_dir / "component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "---\n\n"
        + "# Foo\n\nA fixture component.\n",
    )
    req_rel = "specs/components/foo/requirements/R-FOO-001.md"
    write(
        repo_root / req_rel,
        "# R-FOO-001\n\nFoo behaves as decided in `" + d1 + "`.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\n\nGiven foo\nWhen it runs\nThen it behaves.\n",
    )
    commit_all(repo_root, "Add foo spec citing " + d1)

    # The superseding decision, ratified after the spec file was last touched.
    d2_path = Path(
        spec_scaffolder.new_decision(
            repo_root, "Replacement approach", owners=["team-a"], supersedes=d1
        )
    )
    d2 = d2_path.stem
    assert d2 != d1
    if not d2_path.is_absolute():
        d2_path = repo_root / d2_path
    fm = frontmatter_lines(d2_path.read_text(encoding="utf-8"))
    supersedes_lines = [l for l in fm if l.startswith("supersedes:")]
    assert supersedes_lines == ["supersedes: " + d1]

    spec_scaffolder.ratify(repo_root, d2)
    commit_all(repo_root, "Ratify " + d2)
    spec_scaffolder.record_commit(repo_root, d2)
    commit_all(repo_root, "Record commit for " + d2)

    report = decision_drift_detector.find_decision_drift(repo_root)
    entries = list(field(report, "entries"))

    def matches(entry):
        file_value = Path(str(field(entry, "file"))).as_posix()
        return (
            (file_value == req_rel or file_value.endswith("/" + req_rel))
            and field(entry, "cited_decision") == d1
        )

    matching = [e for e in entries if matches(e)]
    assert matching, "expected drift entry for " + repr((req_rel, d1)) + " in " + repr(entries)
    assert field(matching[0], "superseded_by") == d2