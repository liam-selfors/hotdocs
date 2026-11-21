# hotdocs-criterion: sha256:597c30f34a551413c1136a7223d32be84f8aa1d2d218ac0219dce02d40756854
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
            "-c", "user.name=Test User",
            "-c", "user.email=test@example.invalid",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
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


def ratify_and_record(repo_root, decision_id):
    spec_scaffolder.ratify(repo_root, decision_id)
    commit_all(repo_root, "Ratify " + decision_id)
    spec_scaffolder.record_commit(repo_root, decision_id)
    commit_all(repo_root, "Record ratification commit of " + decision_id)


def test_cs_decision_integrity_001(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init", "-q")
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    write(repo_root / "README.md", "fixture repo\n")
    commit_all(repo_root, "Initial commit")

    # Earlier decision, ratified and committed.
    earlier_path = spec_scaffolder.new_decision(
        repo_root, "Earlier conclusion", owners=["pipeline-team"]
    )
    earlier_id = Path(earlier_path).stem
    commit_all(repo_root, "Add " + earlier_id)
    ratify_and_record(repo_root, earlier_id)

    # A live spec file citing the earlier decision, touched before supersession.
    comp_dir = repo_root / "specs" / "components" / "foo"
    write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    citing_rel = "specs/components/foo/requirements/R-FOO-001.md"
    write(
        repo_root / citing_rel,
        "# R-FOO-001\n"
        "\n"
        "Foo MUST behave as decided in `" + earlier_id + "`.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "\n"
        "Given foo, when it runs, then it behaves.\n",
    )
    commit_all(repo_root, "Add comp-foo citing " + earlier_id)

    # Later decision superseding the earlier one, ratified afterwards.
    later_path = spec_scaffolder.new_decision(
        repo_root,
        "Later conclusion",
        owners=["pipeline-team"],
        supersedes=earlier_id,
    )
    later_id = Path(later_path).stem
    assert later_id != earlier_id
    later_text = Path(later_path).read_text(encoding="utf-8")
    assert ("supersedes: " + earlier_id) in later_text.splitlines()
    commit_all(repo_root, "Add " + later_id)
    ratify_and_record(repo_root, later_id)

    report = decision_drift_detector.find_decision_drift(repo_root)
    entries = field(report, "entries")

    matching = [
        entry
        for entry in entries
        if Path(str(field(entry, "file"))).as_posix().endswith(citing_rel)
        and field(entry, "cited_decision") == earlier_id
    ]
    assert matching, "expected drift entry for " + repr((citing_rel, earlier_id)) + " in " + repr(entries)
    assert field(matching[0], "superseded_by") == later_id