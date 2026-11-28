# hotdocs-criterion: sha256:419477a522aee5386a6795f6936088cecf78c01f4369ee0c9cb265fd83345347
from pathlib import Path

import pytest

import spec_scaffolder


D4_TEXT = (
    "---\n"
    "id: D4\n"
    "title: Earlier decision\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# D4 — Earlier decision\n"
    "\n"
    "## Context\n"
    "\n"
    "TODO.\n"
)


def make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "D4.md").write_text(D4_TEXT, encoding="utf-8")
    return repo_root


def expected_text(decision_id, title, owners_line, builds_on_line=None, supersedes_line=None):
    lines = [
        "---",
        "id: " + decision_id,
        "title: " + title,
        "status: draft",
        owners_line,
    ]
    if builds_on_line is not None:
        lines.append(builds_on_line)
    if supersedes_line is not None:
        lines.append(supersedes_line)
    lines += [
        "---",
        "",
        "# " + decision_id + " — " + title,
        "",
        "## Context",
        "",
        "TODO.",
        "",
        "## Decision",
        "",
        "TODO.",
        "",
        "## Consequences",
        "",
        "TODO.",
    ]
    return "".join(line + "\n" for line in lines)


def decision_files(repo_root):
    decisions = repo_root / "specs" / "decisions"
    return sorted(p.name for p in decisions.iterdir())


def test_new_decision_with_owners_and_builds_on_writes_exact_layout(tmp_path):
    repo_root = make_repo(tmp_path)

    result = spec_scaffolder.new_decision(
        repo_root, "Slugs are ASCII", owners=["team-a"], builds_on=["D4"]
    )

    expected_path = repo_root / "specs" / "decisions" / "D5.md"
    assert Path(result).resolve() == expected_path.resolve()
    assert expected_path.is_file()

    text = expected_path.read_text(encoding="utf-8")
    assert text == expected_text(
        "D5",
        "Slugs are ASCII",
        "owners: [team-a]",
        builds_on_line="builds_on: [D4]",
    )
    assert "builds_on: [D4]" in text.splitlines()
    assert not any(line.startswith("supersedes:") for line in text.splitlines())


def test_new_decision_without_owners_defaults_to_unassigned(tmp_path):
    repo_root = make_repo(tmp_path)

    result = spec_scaffolder.new_decision(repo_root, "No owners")

    path = Path(result)
    if not path.is_absolute():
        path = repo_root / path
    assert path.is_file()
    assert path.resolve().parent == (repo_root / "specs" / "decisions").resolve()

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    owners_lines = [line for line in lines if line.startswith("owners:")]
    assert owners_lines == ["owners: [unassigned]"]
    assert not any(line.startswith("builds_on:") for line in lines)
    assert not any(line.startswith("supersedes:") for line in lines)

    decision_id = path.stem
    assert text == expected_text(decision_id, "No owners", "owners: [unassigned]")


def test_new_decision_unknown_builds_on_raises_and_writes_nothing(tmp_path):
    repo_root = make_repo(tmp_path)
    before = decision_files(repo_root)

    with pytest.raises(ValueError):
        spec_scaffolder.new_decision(repo_root, "x", builds_on=["D99"])

    assert decision_files(repo_root) == before


def test_new_decision_empty_title_raises_and_writes_nothing(tmp_path):
    repo_root = make_repo(tmp_path)
    before = decision_files(repo_root)

    with pytest.raises(ValueError):
        spec_scaffolder.new_decision(repo_root, "")

    assert decision_files(repo_root) == before