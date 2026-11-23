# hotdocs-criterion: sha256:c28bc9b6d5f1fede5178ef927af3f89c071069b46e1eaacbda77cf65e0875bdc
import spec_scaffolder

from pathlib import Path

import pytest


D2_TEXT = (
    "---\n"
    "id: D2\n"
    "title: Two\n"
    "status: ratified\n"
    "owners: [team-a]\n"
    "last_ratified_commit: 0000000\n"
    "---\n"
    "\n"
    "# D2: Two\n"
    "\n"
    "Some body text for decision two.\n"
)


def _abs(repo_root, p):
    p = Path(p)
    if not p.is_absolute():
        p = Path(repo_root) / p
    return p.resolve()


def _closing_frontmatter_index(lines):
    assert lines and lines[0].strip() == "---", "file does not start with frontmatter"
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return i
    raise AssertionError("no closing frontmatter delimiter")


def _snapshot(root):
    snap = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            snap[str(p.relative_to(root))] = p.read_bytes()
    return snap


def _setup(tmp_path):
    repo_root = tmp_path / "repo"
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)
    d2 = decisions / "D2.md"
    d2.write_text(D2_TEXT, encoding="utf-8")
    d3 = spec_scaffolder.new_decision(repo_root, "Replace two", supersedes="D2")
    d3 = _abs(repo_root, d3)
    assert d3.name == "D3.md"
    assert d3.is_file()
    return repo_root, d2, d3


def test_ratify_superseding_record_and_refusals(tmp_path):
    repo_root, d2, d3 = _setup(tmp_path)

    d2_before = d2.read_text(encoding="utf-8").splitlines()
    d3_before = d3.read_text(encoding="utf-8").splitlines()
    assert "status: draft" in d3_before
    assert "supersedes: D2" in d3_before

    result = spec_scaffolder.ratify(repo_root, "D3")

    assert isinstance(result, list)
    assert [_abs(repo_root, p) for p in result] == [d3.resolve(), d2.resolve()]

    # Expected D3: status changed, PENDING-COMMIT appended as last frontmatter line.
    expected_d3 = list(d3_before)
    idx = expected_d3.index("status: draft")
    expected_d3[idx] = "status: ratified"
    close = _closing_frontmatter_index(expected_d3)
    expected_d3.insert(close, "last_ratified_commit: PENDING-COMMIT")

    d3_after = d3.read_text(encoding="utf-8").splitlines()
    assert "status: ratified" in d3_after
    after_close = _closing_frontmatter_index(d3_after)
    assert d3_after[after_close - 1] == "last_ratified_commit: PENDING-COMMIT"
    assert d3_after == expected_d3

    # Expected D2: only the status line changes.
    expected_d2 = list(d2_before)
    idx2 = expected_d2.index("status: ratified")
    expected_d2[idx2] = "status: deprecated"
    d2_after = d2.read_text(encoding="utf-8").splitlines()
    assert "status: deprecated" in d2_after
    assert d2_after == expected_d2

    # Second part: already ratified, and unknown decision.
    snap = _snapshot(repo_root)

    with pytest.raises(LookupError):
        spec_scaffolder.ratify(repo_root, "D3")
    assert _snapshot(repo_root) == snap

    with pytest.raises(LookupError):
        spec_scaffolder.ratify(repo_root, "D40")
    assert _snapshot(repo_root) == snap