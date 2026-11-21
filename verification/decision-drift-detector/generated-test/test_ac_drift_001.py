# hotdocs-criterion: sha256:940cd3c1bb86d544b2cb33d30450c876ed7189b7dcb94bac726a1a25d2aa522f
import subprocess
from pathlib import Path

import decision_drift_detector


GIT_CFG = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]

SPEC_FILE = "specs/components/foo/requirements/R-FOO-001.md"


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
    return git(repo_root, "rev-parse", "--short", "HEAD")


def write(repo_root, rel, text):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def decision_text(did, status, last_ratified_commit=None, supersedes=None):
    lines = [
        "---",
        "id: " + did,
        "title: Decision " + did,
        "status: " + status,
        "owners: [pipeline-team]",
    ]
    if supersedes is not None:
        lines.append("supersedes: " + supersedes)
    if last_ratified_commit is not None:
        lines.append("last_ratified_commit: " + last_ratified_commit)
    lines += ["---", "", "# " + did, "", "Decision body.", ""]
    return "\n".join(lines)


def write_decision(repo_root, did, status, last_ratified_commit=None, supersedes=None):
    write(
        repo_root,
        "specs/decisions/" + did + ".md",
        decision_text(did, status, last_ratified_commit, supersedes),
    )


def record_commit(repo_root, did, status, ratifying_hash, supersedes=None):
    write_decision(repo_root, did, status, ratifying_hash, supersedes)
    commit(repo_root, "record-commit " + did)


def write_component(repo_root):
    write(
        repo_root,
        "specs/components/foo/component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "---\n"
        + "\n"
        + "# foo\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Does foo things.\n",
    )
    write(
        repo_root,
        SPEC_FILE,
        "# R-FOO-001\n\n**R-FOO-001** — The foo MUST follow D17 when it runs.\n",
    )
    write(
        repo_root,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        + "Covers: R-FOO-001\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n"
        + "Given a foo\n"
        + "When it runs\n"
        + "Then it works\n"
        + "```\n",
    )


def init_repo(repo_root):
    git(repo_root, "init", "-q")
    write_component(repo_root)
    write_decision(repo_root, "D17", "ratified", "0000000")
    d17_hash = commit(repo_root, "initial: spec citing D17, D17 ratified")
    record_commit(repo_root, "D17", "ratified", d17_hash)
    return d17_hash


def normalize_file(repo_root, value):
    p = Path(str(value))
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(Path(repo_root).resolve())
        except ValueError:
            pass
    return p.as_posix()


def entries_for(repo_root, report):
    entries = field(report, "entries")
    return [
        e
        for e in entries
        if normalize_file(repo_root, field(e, "file")) == SPEC_FILE
    ]


def test_single_superseder_reported(tmp_path):
    repo_root = tmp_path.resolve()
    d17_hash = init_repo(repo_root)

    # Later commit: D17 deprecated, D31 ratified superseding it.
    write_decision(repo_root, "D17", "deprecated", d17_hash)
    write_decision(repo_root, "D31", "ratified", "0000000", supersedes="D17")
    d31_hash = commit(repo_root, "D31 supersedes D17")
    record_commit(repo_root, "D31", "ratified", d31_hash, supersedes="D17")

    report = decision_drift_detector.find_decision_drift(repo_root)

    matching = entries_for(repo_root, report)
    assert len(matching) == 1, matching
    entry = matching[0]
    assert field(entry, "cited_decision") == "D17"
    assert field(entry, "superseded_by") == "D31"


def test_latest_ratified_superseder_wins(tmp_path):
    repo_root = tmp_path.resolve()
    d17_hash = init_repo(repo_root)

    # D31 supersedes D17, ratified in a later commit.
    write_decision(repo_root, "D17", "deprecated", d17_hash)
    write_decision(repo_root, "D31", "ratified", "0000000", supersedes="D17")
    d31_hash = commit(repo_root, "D31 supersedes D17")
    record_commit(repo_root, "D31", "ratified", d31_hash, supersedes="D17")

    # D32 supersedes D17 too, ratified in a descendant commit of D31's.
    write_decision(repo_root, "D32", "ratified", "0000000", supersedes="D17")
    d32_hash = commit(repo_root, "D32 supersedes D17")
    record_commit(repo_root, "D32", "ratified", d32_hash, supersedes="D17")

    # Sanity: D31's ratifying commit is an ancestor of D32's.
    subprocess.run(
        ["git"] + GIT_CFG + ["merge-base", "--is-ancestor", d31_hash, d32_hash],
        cwd=str(repo_root),
        check=True,
    )

    report = decision_drift_detector.find_decision_drift(repo_root)

    matching = [
        e
        for e in entries_for(repo_root, report)
        if field(e, "cited_decision") == "D17"
    ]
    assert len(matching) == 1, matching
    assert field(matching[0], "superseded_by") == "D32"
    for e in matching:
        assert field(e, "superseded_by") != "D31"