# hotdocs-criterion: sha256:20a7815958c93ea2b90c243616e09c86d29e270579445231d5decda3241bacf6
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
        out.append(line)
    return out


def test_cs_decision_integrity_001(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git(repo_root, "init", "-q")
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    write(repo_root / "README.md", "fixture\n")
    commit_all(repo_root, "initial")

    # Earlier decision D1, ratified and its ratifying commit recorded.
    d1_path = spec_scaffolder.new_decision(repo_root, "Earlier decision", owners=["team-a"])
    d1_id = Path(d1_path).stem
    commit_all(repo_root, "add " + d1_id)
    spec_scaffolder.ratify(repo_root, d1_id)
    commit_all(repo_root, "ratify " + d1_id)
    spec_scaffolder.record_commit(repo_root, d1_id)
    commit_all(repo_root, "record " + d1_id + " commit")

    # A live spec file citing D1, last touched before the superseder exists.
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
        "Foo follows the conclusion of `" + d1_id + "`.\n",
    )
    write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "\n"
        "Given foo, when it runs, then it behaves.\n",
    )
    file_commit = commit_all(repo_root, "add foo citing " + d1_id)

    # Later decision D2 superseding D1, ratified afterwards.
    d2_path = spec_scaffolder.new_decision(
        repo_root, "Superseding decision", owners=["team-a"], supersedes=d1_id
    )
    d2_id = Path(d2_path).stem
    assert d2_id != d1_id
    commit_all(repo_root, "add " + d2_id)
    spec_scaffolder.ratify(repo_root, d2_id)
    commit_all(repo_root, "ratify " + d2_id)
    spec_scaffolder.record_commit(repo_root, d2_id)
    commit_all(repo_root, "record " + d2_id + " commit")

    # Precondition: the superseding record holds the scalar supersedes line.
    d2_file = repo_root / "specs" / "decisions" / (d2_id + ".md")
    fm = [line.strip() for line in frontmatter_lines(d2_file)]
    assert ("supersedes: " + d1_id) in fm

    # The cited file was last touched by file_commit, before D2's ratification.
    last_touch = git(repo_root, "log", "-1", "--format=%H", "--", req_rel)
    assert last_touch == file_commit

    report = decision_drift_detector.find_decision_drift(repo_root)
    entries = field(report, "entries")

    pairs = []
    for entry in entries:
        entry_file = str(field(entry, "file")).replace("\\", "/")
        pairs.append((entry_file, field(entry, "cited_decision")))

    matching = [
        (f, d)
        for (f, d) in pairs
        if d == d1_id and (f == req_rel or f.endswith("/" + req_rel) or f.endswith(req_rel))
    ]
    assert matching, "expected " + repr((req_rel, d1_id)) + " in drift report, got " + repr(pairs)