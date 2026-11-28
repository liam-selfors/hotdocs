# hotdocs-criterion: sha256:7a64980d01abfc862c956c35e568e405e46f78658da22fda4998ba165d8c67e9
"""AC-SCAFFOLD-003: ratify flips draft to ratified, appends the
PENDING-COMMIT line, deprecates the superseded record, and refuses
unknown or already-ratified decisions without changing any file."""

from pathlib import Path

import pytest

import spec_scaffolder


def _write_ratified(repo_root, n, title):
    text = (
        "---\n"
        "id: D" + str(n) + "\n"
        "title: " + title + "\n"
        "status: ratified\n"
        "owners: [team-a]\n"
        "last_ratified_commit: 0000000\n"
        "---\n"
        "\n"
        "# D" + str(n) + " " + title + "\n"
        "\n"
        "Some body text for " + title + ".\n"
    )
    path = repo_root / "specs" / "decisions" / ("D" + str(n) + ".md")
    path.write_text(text, encoding="utf-8")
    return path


def _abs(repo_root, p):
    p = Path(p)
    if not p.is_absolute():
        p = Path(repo_root) / p
    return p.resolve()


def _frontmatter_close_index(lines):
    assert lines[0] == "---", lines
    for i in range(1, len(lines)):
        if lines[i] == "---":
            return i
    raise AssertionError("no closing frontmatter delimiter")


def _snapshot(repo_root):
    decisions = repo_root / "specs" / "decisions"
    return {p.name: p.read_bytes() for p in sorted(decisions.iterdir()) if p.is_file()}


@pytest.fixture
def repo(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True)
    _write_ratified(repo_root, 1, "One")
    d2 = _write_ratified(repo_root, 2, "Two")
    d3 = spec_scaffolder.new_decision(repo_root, "Replace two", supersedes="D2")
    d3 = _abs(repo_root, d3)
    assert d3.name == "D3.md"
    assert d3 == (repo_root / "specs" / "decisions" / "D3.md").resolve()
    return repo_root, d2.resolve(), d3


def test_ac_scaffold_003(repo):
    repo_root, d2, d3 = repo

    d3_before = d3.read_text(encoding="utf-8").split("\n")
    d2_before = d2.read_text(encoding="utf-8").split("\n")
    assert d3_before.count("status: draft") == 1
    assert "supersedes: D2" in d3_before
    assert d2_before.count("status: ratified") == 1

    result = spec_scaffolder.ratify(repo_root, "D3")
    paths = [_abs(repo_root, p) for p in result]
    assert paths == [d3, d2]

    # D3: status flipped, PENDING-COMMIT appended as last frontmatter line.
    d3_after = d3.read_text(encoding="utf-8").split("\n")
    assert "status: ratified" in d3_after
    close = _frontmatter_close_index(d3_after)
    assert d3_after[close - 1] == "last_ratified_commit: PENDING-COMMIT"

    expected_d3 = list(d3_before)
    expected_d3[expected_d3.index("status: draft")] = "status: ratified"
    before_close = _frontmatter_close_index(expected_d3)
    expected_d3.insert(before_close, "last_ratified_commit: PENDING-COMMIT")
    assert d3_after == expected_d3

    # D2: only its status line changes, to deprecated.
    d2_after = d2.read_text(encoding="utf-8").split("\n")
    assert "status: deprecated" in d2_after
    expected_d2 = list(d2_before)
    expected_d2[expected_d2.index("status: ratified")] = "status: deprecated"
    assert d2_after == expected_d2

    # Second ratify of D3: already ratified -> LookupError, nothing changes.
    snap = _snapshot(repo_root)
    with pytest.raises(LookupError):
        spec_scaffolder.ratify(repo_root, "D3")
    assert _snapshot(repo_root) == snap

    # Unknown decision D40 -> LookupError, nothing changes.
    with pytest.raises(LookupError):
        spec_scaffolder.ratify(repo_root, "D40")
    assert _snapshot(repo_root) == snap
    assert not (repo_root / "specs" / "decisions" / "D40.md").exists()