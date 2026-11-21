# hotdocs-criterion: sha256:c33387cb8b63dd6c742c53a6bce3a4ea598babf75f4ec828911e273a1824e34a
from pathlib import Path

import pytest

import spec_scaffolder


D4_TEXT = (
    "---\n"
    "id: D4\n"
    "title: An earlier decision\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# D4 — An earlier decision\n"
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


def snapshot(repo_root):
    decisions = repo_root / "specs" / "decisions"
    return {
        p.name: p.read_bytes() for p in sorted(decisions.iterdir())
    }


def body(decision_id, title):
    return (
        "---\n"
        + "\n"
        + "# " + decision_id + " — " + title + "\n"
        + "\n"
        + "## Context\n"
        + "\n"
        + "TODO.\n"
        + "\n"
        + "## Decision\n"
        + "\n"
        + "TODO.\n"
        + "\n"
        + "## Consequences\n"
        + "\n"
        + "TODO.\n"
    )


def test_new_decision_with_owners_and_builds_on(tmp_path):
    repo_root = make_repo(tmp_path)

    result = spec_scaffolder.new_decision(
        repo_root, "Slugs are ASCII", owners=["team-a"], builds_on=["D4"]
    )

    expected_path = repo_root / "specs" / "decisions" / "D5.md"
    assert Path(result).resolve() == expected_path.resolve()
    assert expected_path.is_file()

    expected = (
        "---\n"
        + "id: D5\n"
        + "title: Slugs are ASCII\n"
        + "status: draft\n"
        + "owners: [team-a]\n"
        + "builds_on: [D4]\n"
        + body("D5", "Slugs are ASCII")
    )
    text = expected_path.read_text(encoding="utf-8")
    assert text == expected
    assert "builds_on: [D4]\n" in text.splitlines(keepends=True)
    assert not any(line.startswith("supersedes:") for line in text.splitlines())


def test_new_decision_defaults_owners_and_omits_optional_lines(tmp_path):
    repo_root = make_repo(tmp_path)

    result = spec_scaffolder.new_decision(repo_root, "No owners")

    path = Path(result)
    if not path.is_absolute():
        path = repo_root / path
    assert path.is_file()
    assert path.resolve().parent == (repo_root / "specs" / "decisions").resolve()

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert "owners: [unassigned]" in lines
    assert not any(line.startswith("builds_on:") for line in lines)
    assert not any(line.startswith("supersedes:") for line in lines)

    decision_id = path.stem
    expected = (
        "---\n"
        + "id: " + decision_id + "\n"
        + "title: No owners\n"
        + "status: draft\n"
        + "owners: [unassigned]\n"
        + body(decision_id, "No owners")
    )
    assert text == expected


def test_new_decision_unknown_builds_on_raises_and_writes_nothing(tmp_path):
    repo_root = make_repo(tmp_path)
    before = snapshot(repo_root)

    with pytest.raises(ValueError):
        spec_scaffolder.new_decision(repo_root, "x", builds_on=["D99"])

    assert snapshot(repo_root) == before


def test_new_decision_empty_title_raises_and_writes_nothing(tmp_path):
    repo_root = make_repo(tmp_path)
    before = snapshot(repo_root)

    with pytest.raises(ValueError):
        spec_scaffolder.new_decision(repo_root, "")

    assert snapshot(repo_root) == before