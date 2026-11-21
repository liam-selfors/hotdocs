# hotdocs-criterion: sha256:3c3c90aff98a01b71b71973790a39f2959aba00dc8fa2c40d1dc2e1b61efd886
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


def expected_text(decision_id, title, owners_line, builds_on_line=None):
    lines = [
        "---",
        "id: " + decision_id,
        "title: " + title,
        "status: draft",
        owners_line,
    ]
    if builds_on_line is not None:
        lines.append(builds_on_line)
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


def listing(repo_root):
    decisions = repo_root / "specs" / "decisions"
    return sorted(p.name for p in decisions.iterdir())


def test_new_decision_with_owners_and_builds_on(tmp_path):
    repo_root = make_repo(tmp_path)
    result = spec_scaffolder.new_decision(
        repo_root, "Slugs are ASCII", owners=["team-a"], builds_on=["D4"]
    )
    expected_path = repo_root / "specs" / "decisions" / "D5.md"
    assert Path(result).resolve() == expected_path.resolve()
    assert expected_path.is_file()
    text = expected_path.read_text(encoding="utf-8")
    assert text == expected_text(
        "D5", "Slugs are ASCII", "owners: [team-a]", "builds_on: [D4]"
    )
    assert "supersedes" not in text


def test_new_decision_defaults(tmp_path):
    repo_root = make_repo(tmp_path)
    spec_scaffolder.new_decision(
        repo_root, "Slugs are ASCII", owners=["team-a"], builds_on=["D4"]
    )
    result = Path(spec_scaffolder.new_decision(repo_root, "No owners"))
    assert result.is_file()
    assert result.parent.resolve() == (repo_root / "specs" / "decisions").resolve()
    decision_id = result.stem
    text = result.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert "owners: [unassigned]" in lines
    assert not any(line.startswith("builds_on:") for line in lines)
    assert not any(line.startswith("supersedes:") for line in lines)
    assert text == expected_text(decision_id, "No owners", "owners: [unassigned]")


def test_new_decision_unknown_builds_on_raises(tmp_path):
    repo_root = make_repo(tmp_path)
    before = listing(repo_root)
    with pytest.raises(ValueError):
        spec_scaffolder.new_decision(repo_root, "x", builds_on=["D99"])
    assert listing(repo_root) == before


def test_new_decision_empty_title_raises(tmp_path):
    repo_root = make_repo(tmp_path)
    before = listing(repo_root)
    with pytest.raises(ValueError):
        spec_scaffolder.new_decision(repo_root, "")
    assert listing(repo_root) == before