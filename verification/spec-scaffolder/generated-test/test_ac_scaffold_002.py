import spec_scaffolder

from pathlib import Path

import pytest


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
    "\n"
    "## Decision\n"
    "\n"
    "TODO.\n"
    "\n"
    "## Consequences\n"
    "\n"
    "TODO.\n"
)


def _make_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "D4.md").write_text(D4_TEXT, encoding="utf-8")
    return repo_root


def _read_exact(path: Path) -> str:
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _resolve_returned(repo_root: Path, result) -> Path:
    p = Path(result)
    if not p.is_absolute():
        p = repo_root / p
    return p.resolve()


def _listing(repo_root: Path):
    decisions = repo_root / "specs" / "decisions"
    return sorted(
        str(p.relative_to(decisions)) for p in decisions.rglob("*")
    )


def test_new_decision_writes_exact_layout_with_builds_on(tmp_path):
    repo_root = _make_repo(tmp_path)

    result = spec_scaffolder.new_decision(
        repo_root, "Slugs are ASCII", owners=["team-a"], builds_on=["D4"]
    )

    expected_path = (repo_root / "specs" / "decisions" / "D5.md").resolve()
    assert _resolve_returned(repo_root, result) == expected_path
    assert expected_path.is_file()

    expected_text = (
        "---\n"
        "id: D5\n"
        "title: Slugs are ASCII\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "builds_on: [D4]\n"
        "---\n"
        "\n"
        "# D5 — Slugs are ASCII\n"
        "\n"
        "## Context\n"
        "\n"
        "TODO.\n"
        "\n"
        "## Decision\n"
        "\n"
        "TODO.\n"
        "\n"
        "## Consequences\n"
        "\n"
        "TODO.\n"
    )
    text = _read_exact(expected_path)
    assert text == expected_text
    assert "builds_on: [D4]" in text.splitlines()
    assert not any(line.startswith("supersedes:") for line in text.splitlines())


def test_new_decision_default_owners_and_no_optional_lines(tmp_path):
    repo_root = _make_repo(tmp_path)

    result = spec_scaffolder.new_decision(repo_root, "No owners")

    written = _resolve_returned(repo_root, result)
    assert written.is_file()
    assert written.parent == (repo_root / "specs" / "decisions").resolve()

    lines = _read_exact(written).splitlines()
    owners_lines = [line for line in lines if line.startswith("owners:")]
    assert owners_lines == ["owners: [unassigned]"]
    assert not any(line.startswith("builds_on:") for line in lines)
    assert not any(line.startswith("supersedes:") for line in lines)


def test_new_decision_unknown_builds_on_raises_and_writes_nothing(tmp_path):
    repo_root = _make_repo(tmp_path)
    before = _listing(repo_root)

    with pytest.raises(ValueError):
        spec_scaffolder.new_decision(repo_root, "x", builds_on=["D99"])

    assert _listing(repo_root) == before


def test_new_decision_empty_title_raises_and_writes_nothing(tmp_path):
    repo_root = _make_repo(tmp_path)
    before = _listing(repo_root)

    with pytest.raises(ValueError):
        spec_scaffolder.new_decision(repo_root, "")

    assert _listing(repo_root) == before