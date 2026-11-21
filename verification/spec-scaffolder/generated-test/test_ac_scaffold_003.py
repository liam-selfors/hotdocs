# hotdocs-criterion: sha256:08e7dd541136b29046b1f84086449df96814450d4df55ce155e36c03ca210296
import spec_scaffolder

from pathlib import Path

import pytest


def _write(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _closing_index(lines):
    assert lines[0] == "---"
    for i in range(1, len(lines)):
        if lines[i] == "---":
            return i
    raise AssertionError("no closing frontmatter delimiter")


def _abs(repo_root, p):
    p = Path(p)
    if not p.is_absolute():
        p = Path(repo_root) / p
    return p.resolve()


def _snapshot(repo_root):
    root = Path(repo_root)
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _build(tmp_path):
    repo_root = tmp_path / "repo"
    decisions = repo_root / "specs" / "decisions"
    decisions.mkdir(parents=True)
    _write(
        decisions / "D1.md",
        [
            "---",
            "id: D1",
            "title: First decision",
            "status: ratified",
            "owners: [team-a]",
            "last_ratified_commit: 0000000",
            "---",
            "",
            "# D1",
            "",
            "Body one.",
        ],
    )
    _write(
        decisions / "D2.md",
        [
            "---",
            "id: D2",
            "title: Second decision",
            "status: ratified",
            "owners: [team-a, team-b]",
            "last_ratified_commit: 0000000",
            "---",
            "",
            "# D2",
            "",
            "Body two.",
        ],
    )
    d3 = spec_scaffolder.new_decision(repo_root, "Replace two", supersedes="D2")
    d3_abs = _abs(repo_root, d3)
    assert d3_abs == (decisions / "D3.md").resolve()
    return repo_root, decisions


def test_ac_scaffold_003_ratify_and_deprecate_superseded(tmp_path):
    repo_root, decisions = _build(tmp_path)
    d2_path = decisions / "D2.md"
    d3_path = decisions / "D3.md"

    d2_before = d2_path.read_text(encoding="utf-8").split("\n")
    d3_before = d3_path.read_text(encoding="utf-8").split("\n")
    assert "status: draft" in d3_before[: _closing_index(d3_before)]

    result = spec_scaffolder.ratify(repo_root, "D3")

    result_abs = [_abs(repo_root, p) for p in result]
    assert result_abs == [d3_path.resolve(), d2_path.resolve()]

    d3_after = d3_path.read_text(encoding="utf-8").split("\n")
    d2_after = d2_path.read_text(encoding="utf-8").split("\n")

    # Expected D3: status line flipped, PENDING-COMMIT added as last frontmatter line.
    close3 = _closing_index(d3_before)
    expected_d3 = list(d3_before)
    idx = expected_d3.index("status: draft")
    assert idx < close3
    expected_d3[idx] = "status: ratified"
    expected_d3.insert(close3, "last_ratified_commit: PENDING-COMMIT")
    assert d3_after == expected_d3

    close3_after = _closing_index(d3_after)
    assert d3_after[close3_after - 1] == "last_ratified_commit: PENDING-COMMIT"
    assert "status: ratified" in d3_after[:close3_after]

    # Expected D2: only the status line changes, to deprecated.
    expected_d2 = list(d2_before)
    idx2 = expected_d2.index("status: ratified")
    assert idx2 < _closing_index(d2_before)
    expected_d2[idx2] = "status: deprecated"
    assert d2_after == expected_d2


def test_ac_scaffold_003_already_ratified_and_unknown_raise(tmp_path):
    repo_root, decisions = _build(tmp_path)
    spec_scaffolder.ratify(repo_root, "D3")

    before = _snapshot(repo_root)

    with pytest.raises(LookupError):
        spec_scaffolder.ratify(repo_root, "D3")
    assert _snapshot(repo_root) == before

    with pytest.raises(LookupError):
        spec_scaffolder.ratify(repo_root, "D40")
    assert _snapshot(repo_root) == before