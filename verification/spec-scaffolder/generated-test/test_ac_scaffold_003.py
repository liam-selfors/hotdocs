import spec_scaffolder

from pathlib import Path

import pytest


def _write_ratified(decisions: Path, n: int, title: str) -> Path:
    path = decisions / f"D{n}.md"
    path.write_text(
        "---\n"
        f"id: D{n}\n"
        f"title: {title}\n"
        "status: ratified\n"
        "owners: [team-a]\n"
        "last_ratified_commit: abc1234\n"
        "---\n"
        "\n"
        f"# D{n}: {title}\n"
        "\n"
        "Some body text for this decision.\n"
        "\n"
        "More body text, with status: ratified mentioned in prose.\n",
        encoding="utf-8",
    )
    return path


def _norm(repo_root: Path, p) -> Path:
    p = Path(str(p))
    if not p.is_absolute():
        p = repo_root / p
    return p.resolve()


def _frontmatter_close_index(lines):
    assert lines and lines[0].strip() == "---", lines
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return i
    raise AssertionError("no closing frontmatter delimiter: %r" % (lines,))


def _snapshot(root: Path):
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.fixture
def repo(tmp_path):
    repo_root = tmp_path.resolve() / "repo"
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)
    _write_ratified(decisions, 1, "First decision")
    d2 = _write_ratified(decisions, 2, "Second decision")
    d3 = spec_scaffolder.new_decision(repo_root, "Replace two", supersedes="D2")
    d3 = _norm(repo_root, d3)
    assert d3 == (decisions / "D3.md").resolve()
    return repo_root, d3, d2.resolve()


def test_ac_scaffold_003_ratify_and_deprecate_superseded(repo):
    repo_root, d3, d2 = repo

    d3_before = d3.read_text(encoding="utf-8").splitlines()
    d2_before = d2.read_text(encoding="utf-8").splitlines()
    assert "status: draft" in d3_before
    assert "status: ratified" in d2_before

    result = spec_scaffolder.ratify(repo_root, "D3")

    assert [_norm(repo_root, p) for p in result] == [d3, d2]

    # Expected D3: status flipped, PENDING-COMMIT appended as last frontmatter line.
    expected_d3 = list(d3_before)
    status_idx = expected_d3.index("status: draft")
    expected_d3[status_idx] = "status: ratified"
    close = _frontmatter_close_index(expected_d3)
    expected_d3.insert(close, "last_ratified_commit: PENDING-COMMIT")

    d3_after = d3.read_text(encoding="utf-8").splitlines()
    assert d3_after == expected_d3
    assert "status: ratified" in d3_after
    after_close = _frontmatter_close_index(d3_after)
    assert d3_after[after_close - 1] == "last_ratified_commit: PENDING-COMMIT"

    # Expected D2: only its status line changes, to deprecated.
    expected_d2 = list(d2_before)
    d2_close = _frontmatter_close_index(expected_d2)
    status_lines = [
        i for i in range(1, d2_close) if expected_d2[i].startswith("status:")
    ]
    assert len(status_lines) == 1
    expected_d2[status_lines[0]] = "status: deprecated"

    d2_after = d2.read_text(encoding="utf-8").splitlines()
    assert d2_after == expected_d2
    assert "status: deprecated" in d2_after


def test_ac_scaffold_003_ratify_again_or_unknown_raises_lookup_error(repo):
    repo_root, d3, d2 = repo

    spec_scaffolder.ratify(repo_root, "D3")

    before = _snapshot(repo_root)

    with pytest.raises(LookupError):
        spec_scaffolder.ratify(repo_root, "D3")
    assert _snapshot(repo_root) == before

    with pytest.raises(LookupError):
        spec_scaffolder.ratify(repo_root, "D40")
    assert _snapshot(repo_root) == before
    assert not (repo_root / "specs" / "decisions" / "D40.md").exists()