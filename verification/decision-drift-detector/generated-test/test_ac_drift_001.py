# hotdocs-criterion: sha256:cae59204aaaeccac79865437912daee6068c7cf955881b7f40b23c561da73719
"""AC-DRIFT-001: find_decision_drift follows `supersedes` edges forward to
the latest (by ratification order) superseding decision."""

import subprocess
from pathlib import Path

import decision_drift_detector


SPEC_FILE = "specs/components/foo/requirements/R-FOO-001.md"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def git(repo, *args):
    cmd = [
        "git",
        "-c", "user.name=t",
        "-c", "user.email=t@t",
        "-c", "commit.gpgsign=false",
    ] + list(args)
    result = subprocess.run(
        cmd, cwd=str(repo), check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def commit(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def short_head(repo):
    return git(repo, "rev-parse", "--short", "HEAD")


def write(repo, rel, text):
    path = Path(repo) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def decision_text(decision_id, status, ratified_commit=None, supersedes=None):
    lines = [
        "---",
        "id: " + decision_id,
        "title: Decision " + decision_id,
        "status: " + status,
        "owners: [pipeline-team]",
    ]
    if supersedes is not None:
        lines.append("supersedes: " + supersedes)
    if ratified_commit is not None:
        lines.append("last_ratified_commit: " + ratified_commit)
    lines += ["---", "", "# " + decision_id, "", "Decision body.", ""]
    return "\n".join(lines)


def decision_path(decision_id):
    return "specs/decisions/" + decision_id + ".md"


def ratify(repo, decision_id, supersedes=None, extra_writes=None):
    """Commit the decision as ratified (together with any extra writes, in
    the same ratifying commit), then record that commit's short hash in
    last_ratified_commit and commit again, as `decision record-commit` does.
    Returns the ratifying commit's short hash."""
    write(
        repo,
        decision_path(decision_id),
        decision_text(decision_id, "ratified", "0000000", supersedes),
    )
    for rel, text in (extra_writes or {}).items():
        write(repo, rel, text)
    commit(repo, "ratify " + decision_id)
    ratified = short_head(repo)
    write(
        repo,
        decision_path(decision_id),
        decision_text(decision_id, "ratified", ratified, supersedes),
    )
    commit(repo, "record commit for " + decision_id)
    return ratified


def write_component(repo):
    write(
        repo,
        "specs/components/foo/component.md",
        "\n".join([
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
            "Does foo things.",
            "",
        ]),
    )
    write(
        repo,
        SPEC_FILE,
        "# R-FOO-001\n\n**R-FOO-001** - The component MUST behave as `D17` states.\n",
    )
    write(
        repo,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven foo\nWhen bar\nThen baz\n```\n",
    )


def init_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    return repo


def normalize_file(repo, value):
    p = Path(str(value))
    if p.is_absolute():
        try:
            p = p.resolve().relative_to(Path(repo).resolve())
        except ValueError:
            pass
    return p.as_posix()


def entries_for(repo, report, rel_file, cited=None):
    out = []
    for entry in field(report, "entries"):
        if normalize_file(repo, field(entry, "file")) != rel_file:
            continue
        if cited is not None and field(entry, "cited_decision") != cited:
            continue
        out.append(entry)
    return out


def test_single_superseder_reported(tmp_path):
    repo = init_repo(tmp_path)

    h17 = ratify(repo, "D17")

    write_component(repo)
    commit(repo, "spec citing D17")

    # Later commit: D17 deprecated, D31 ratified with supersedes: D17.
    ratify(
        repo,
        "D31",
        supersedes="D17",
        extra_writes={
            decision_path("D17"): decision_text("D17", "deprecated", h17),
        },
    )

    report = decision_drift_detector.find_decision_drift(repo)

    matching = entries_for(repo, report, SPEC_FILE)
    assert len(matching) == 1, matching
    entry = matching[0]
    assert field(entry, "cited_decision") == "D17"
    assert field(entry, "superseded_by") == "D31"


def test_latest_ratified_superseder_wins(tmp_path):
    repo = init_repo(tmp_path)

    h17 = ratify(repo, "D17")

    write_component(repo)
    commit(repo, "spec citing D17")

    ratify(
        repo,
        "D31",
        supersedes="D17",
        extra_writes={
            decision_path("D17"): decision_text("D17", "deprecated", h17),
        },
    )
    # D32's ratification commit is a descendant of D31's.
    ratify(repo, "D32", supersedes="D17")

    report = decision_drift_detector.find_decision_drift(repo)

    matching = entries_for(repo, report, SPEC_FILE, cited="D17")
    assert len(matching) == 1, matching
    assert field(matching[0], "superseded_by") == "D32"
    for entry in entries_for(repo, report, SPEC_FILE):
        assert field(entry, "superseded_by") != "D31"