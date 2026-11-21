# hotdocs-criterion: sha256:8fe1966bdccc61dc6982434602002fef2faa6a09ac558223c26ceba176e25702
from pathlib import Path

import pytest

import spec_scaffolder


D1_TEXT = (
    "---\n"
    "id: D1\n"
    "title: First decision\n"
    "status: ratified\n"
    "owners: [team-a]\n"
    "last_ratified_commit: 0000000\n"
    "---\n"
    "\n"
    "# D1: First decision\n"
    "\n"
    "Body of the first decision.\n"
)

D2_TEXT = (
    "---\n"
    "id: D2\n"
    "title: Second decision\n"
    "status: ratified\n"
    "owners: [team-a, team-b]\n"
    "last_ratified_commit: 0000000\n"
    "---\n"
    "\n"
    "# D2: Second decision\n"
    "\n"
    "Body of the second decision.\n"
    "status: this body line is not frontmatter\n"
)


def _snapshot(decisions_dir):
    return {
        p.name: p.read_bytes()
        for p in sorted(decisions_dir.iterdir())
        if p.is_file()
    }


def _frontmatter_close_index(lines):
    assert lines[0] == "---", "file does not start with frontmatter"
    for i in range(1, len(lines)):
        if lines[i] == "---":
            return i
    raise AssertionError("frontmatter is not closed")


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "D1.md").write_text(D1_TEXT)
    (decisions / "D2.md").write_text(D2_TEXT)
    return repo_root, decisions


def test_ac_scaffold_003(tmp_path):
    repo_root, decisions = _build_repo(tmp_path)

    d3_path = spec_scaffolder.new_decision(repo_root, "Replace two", supersedes="D2")
    d3_path = Path(d3_path)
    if not d3_path.is_absolute():
        d3_path = repo_root / d3_path
    assert d3_path.name == "D3.md"
    assert d3_path.resolve() == (decisions / "D3.md").resolve()

    d3_before = (decisions / "D3.md").read_text()
    d2_before = (decisions / "D2.md").read_text()
    d1_before_bytes = (decisions / "D1.md").read_bytes()

    d3_before_lines = d3_before.split("\n")
    assert "status: draft" in d3_before_lines
    assert "supersedes: D2" in d3_before_lines

    result = spec_scaffolder.ratify(repo_root, "D3")

    result_paths = []
    for p in result:
        p = Path(p)
        if not p.is_absolute():
            p = repo_root / p
        result_paths.append(p.resolve())
    assert result_paths == [
        (decisions / "D3.md").resolve(),
        (decisions / "D2.md").resolve(),
    ]

    # D3: status changed, last_ratified_commit appended as last frontmatter line.
    d3_after_lines = (decisions / "D3.md").read_text().split("\n")
    expected_d3 = [
        "status: ratified" if line == "status: draft" else line
        for line in d3_before_lines
    ]
    close = _frontmatter_close_index(expected_d3)
    expected_d3.insert(close, "last_ratified_commit: PENDING-COMMIT")
    assert d3_after_lines == expected_d3

    after_close = _frontmatter_close_index(d3_after_lines)
    assert d3_after_lines[after_close - 1] == "last_ratified_commit: PENDING-COMMIT"
    assert "status: ratified" in d3_after_lines[:after_close]

    # D2: only its frontmatter status line changed to deprecated.
    d2_before_lines = d2_before.split("\n")
    d2_after_lines = (decisions / "D2.md").read_text().split("\n")
    d2_close = _frontmatter_close_index(d2_before_lines)
    expected_d2 = list(d2_before_lines)
    for i in range(1, d2_close):
        if expected_d2[i].startswith("status:"):
            expected_d2[i] = "status: deprecated"
            break
    assert d2_after_lines == expected_d2
    assert "status: deprecated" in d2_after_lines

    # Unrelated record untouched.
    assert (decisions / "D1.md").read_bytes() == d1_before_bytes

    # Second part: re-ratifying D3 and ratifying a missing D40 both raise, changing nothing.
    snapshot = _snapshot(decisions)

    with pytest.raises(LookupError):
        spec_scaffolder.ratify(repo_root, "D3")
    assert _snapshot(decisions) == snapshot

    with pytest.raises(LookupError):
        spec_scaffolder.ratify(repo_root, "D40")
    assert _snapshot(decisions) == snapshot
    assert not (decisions / "D40.md").exists()