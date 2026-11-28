# hotdocs-criterion: sha256:f565c3a69123ce8e1e329ea40f2deb51dcac84bc079b5a46337a19816607b933
import subprocess
from pathlib import Path

import decision_drift_detector
import spec_scaffolder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo_root, *args):
    result = subprocess.run(
        [
            "git",
            "-c", "user.name=Test",
            "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def commit_all(repo_root, message):
    git(repo_root, "add", "-A")
    git(repo_root, "commit", "-q", "-m", message)
    return git(repo_root, "rev-parse", "HEAD")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_cs_decision_integrity_001_superseded_citation_in_drift_report(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init", "-q")
    (repo_root / "specs" / "decisions").mkdir(parents=True)

    # Earlier decision: created, ratified, committed, its commit recorded.
    d1_path = spec_scaffolder.new_decision(repo_root, "Earlier decision", owners=["team-a"])
    d1_id = Path(d1_path).stem
    spec_scaffolder.ratify(repo_root, d1_id)
    commit_all(repo_root, "ratify " + d1_id)
    spec_scaffolder.record_commit(repo_root, d1_id)
    commit_all(repo_root, "record commit " + d1_id)

    # A live spec file citing the earlier decision, committed now and never touched again.
    comp_dir = repo_root / "specs" / "components" / "foo"
    write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    req_rel = "specs/components/foo/requirements/R-FOO-001.md"
    write(
        repo_root / req_rel,
        "# R-FOO-001\n"
        "\n"
        "Foo MUST behave as decided in `" + d1_id + "`.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "\n"
        "Foo behaves as required.\n",
    )
    commit_all(repo_root, "add foo citing " + d1_id)

    # Later decision superseding the earlier one, then ratified after the citing file's commit.
    d2_path = spec_scaffolder.new_decision(
        repo_root, "Later decision", owners=["team-a"], supersedes=d1_id
    )
    d2_path = Path(d2_path)
    if not d2_path.is_absolute():
        d2_path = repo_root / d2_path
    d2_id = d2_path.stem
    assert d2_id != d1_id

    d2_text = d2_path.read_text(encoding="utf-8")
    lines = [line.rstrip() for line in d2_text.splitlines()]
    assert "supersedes: " + d1_id in lines
    assert not any(line.startswith("supersedes: [") for line in lines)

    spec_scaffolder.ratify(repo_root, d2_id)
    commit_all(repo_root, "ratify " + d2_id)
    spec_scaffolder.record_commit(repo_root, d2_id)
    commit_all(repo_root, "record commit " + d2_id)

    report = decision_drift_detector.find_decision_drift(repo_root)
    entries = list(field(report, "entries"))

    matching = []
    for entry in entries:
        file_value = Path(str(field(entry, "file"))).as_posix()
        if file_value.endswith(req_rel) and field(entry, "cited_decision") == d1_id:
            matching.append(entry)

    assert matching, "expected drift entry for " + repr((req_rel, d1_id)) + ", got " + repr(entries)
    assert field(matching[0], "superseded_by") == d2_id