# hotdocs-criterion: sha256:d887dcf47d5ef072cac67d80be9cbcf52c4cb6391959e2354fd1e78313456682
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


def body(id_, title):
    return (
        "---\n"
        + "\n# " + id_ + " — " + title + "\n"
        + "\n## Context\n\nTODO.\n"
        + "\n## Decision\n\nTODO.\n"
        + "\n## Consequences\n\nTODO.\n"
    )


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

    expected_text = (
        "---\n"
        "id: D5\n"
        "title: Slugs are ASCII\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "builds_on: [D4]\n"
        + body("D5", "Slugs are ASCII")
    )
    text = expected_path.read_text(encoding="utf-8")
    assert text == expected_text
    assert "builds_on: [D4]\n" in text.splitlines(keepends=True)
    assert not any(line.startswith("supersedes:") for line in text.splitlines())


def test_new_decision_default_owners_and_no_links(tmp_path):
    repo_root = make_repo(tmp_path)

    result = spec_scaffolder.new_decision(repo_root, "No owners")

    path = Path(result)
    if not path.is_absolute():
        path = repo_root / path
    assert path.is_file()
    assert path.parent.resolve() == (repo_root / "specs" / "decisions").resolve()

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert "owners: [unassigned]" in lines
    assert not any(line.startswith("builds_on:") for line in lines)
    assert not any(line.startswith("supersedes:") for line in lines)

    id_ = path.stem
    expected_text = (
        "---\n"
        "id: " + id_ + "\n"
        "title: No owners\n"
        "status: draft\n"
        "owners: [unassigned]\n"
        + body(id_, "No owners")
    )
    assert text == expected_text


def test_new_decision_unknown_builds_on_raises_and_writes_nothing(tmp_path):
    repo_root = make_repo(tmp_path)
    before = listing(repo_root)

    with pytest.raises(ValueError):
        spec_scaffolder.new_decision(repo_root, "x", builds_on=["D99"])

    assert listing(repo_root) == before


def test_new_decision_empty_title_raises_and_writes_nothing(tmp_path):
    repo_root = make_repo(tmp_path)
    before = listing(repo_root)

    with pytest.raises(ValueError):
        spec_scaffolder.new_decision(repo_root, "")

    assert listing(repo_root) == before