import os
from pathlib import Path

import citation_checker


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _decision(repo_root: Path, num: int, status: str, supersedes=None) -> None:
    lines = [
        "---",
        f"id: D{num}",
        f"title: Synthetic decision number {num}",
        f"status: {status}",
        "owners: [test-owner]",
    ]
    if status == "ratified":
        lines.append("last_ratified_commit: 0000000000000000000000000000000000000000")
    if supersedes is not None:
        lines.append(f"supersedes: {supersedes}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Synthetic decision {num}")
    lines.append("")
    lines.append("A synthetic decision record used only as a test fixture.")
    lines.append("")
    _write(repo_root / "specs" / "decisions" / f"D{num}.md", "\n".join(lines))


def _make_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True, exist_ok=True)
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Synthetic term** — a term used only by this fixture.\n",
    )
    return repo_root


def _norm(path_value) -> str:
    return str(path_value).replace("\\", "/")


def _cite4(findings):
    assert isinstance(findings, list)
    return [f for f in findings if _get(f, "rule_id") == "R-CITE-004"]


def _for_file(findings, rel):
    return [f for f in findings if _norm(_get(f, "file")) == rel]


def _check_shape(finding):
    assert _get(finding, "severity") in ("fail", "warn")
    line = _get(finding, "line")
    assert isinstance(line, int) and not isinstance(line, bool)
    assert line >= 1
    assert isinstance(_get(finding, "message"), str)
    assert _get(finding, "message")
    assert not os.path.isabs(_norm(_get(finding, "file")))


def test_supersedes_nonexistent_decision_is_flagged(tmp_path):
    repo_root = _make_repo(tmp_path)
    _decision(repo_root, 100, "draft", supersedes="D150")

    findings = _cite4(citation_checker.check(repo_root))
    mine = _for_file(findings, "specs/decisions/D100.md")
    assert len(mine) >= 1, findings
    for f in mine:
        _check_shape(f)


def test_supersedes_still_ratified_decision_is_flagged_naming_it(tmp_path):
    repo_root = _make_repo(tmp_path)
    _decision(repo_root, 101, "draft", supersedes="D102")
    _decision(repo_root, 102, "ratified")

    findings = _cite4(citation_checker.check(repo_root))
    mine = _for_file(findings, "specs/decisions/D101.md")
    assert len(mine) >= 1, findings
    for f in mine:
        _check_shape(f)
    assert any("D102" in (_get(f, "message") or "") for f in mine), mine


def test_supersedes_draft_decision_is_flagged_naming_it(tmp_path):
    repo_root = _make_repo(tmp_path)
    _decision(repo_root, 110, "draft", supersedes="D111")
    _decision(repo_root, 111, "draft")

    findings = _cite4(citation_checker.check(repo_root))
    mine = _for_file(findings, "specs/decisions/D110.md")
    assert len(mine) >= 1, findings
    assert any("D111" in (_get(f, "message") or "") for f in mine), mine


def test_orphan_deprecated_decision_is_flagged(tmp_path):
    repo_root = _make_repo(tmp_path)
    _decision(repo_root, 103, "deprecated")
    _decision(repo_root, 120, "draft")

    findings = _cite4(citation_checker.check(repo_root))
    mine = _for_file(findings, "specs/decisions/D103.md")
    assert len(mine) >= 1, findings
    for f in mine:
        _check_shape(f)
    assert _for_file(findings, "specs/decisions/D120.md") == []


def test_consistent_supersession_produces_no_finding(tmp_path):
    repo_root = _make_repo(tmp_path)
    _decision(repo_root, 104, "draft", supersedes="D105")
    _decision(repo_root, 105, "deprecated")

    findings = _cite4(citation_checker.check(repo_root))
    assert _for_file(findings, "specs/decisions/D104.md") == [], findings
    assert _for_file(findings, "specs/decisions/D105.md") == [], findings


def test_supersedes_of_informal_d1_to_d14_is_exempt(tmp_path):
    repo_root = _make_repo(tmp_path)
    _decision(repo_root, 106, "draft", supersedes="D3")

    findings = _cite4(citation_checker.check(repo_root))
    assert _for_file(findings, "specs/decisions/D106.md") == [], findings


def test_all_three_cases_together_flag_only_offending_records(tmp_path):
    repo_root = _make_repo(tmp_path)
    _decision(repo_root, 100, "draft", supersedes="D150")
    _decision(repo_root, 101, "draft", supersedes="D102")
    _decision(repo_root, 102, "ratified")
    _decision(repo_root, 103, "deprecated")
    _decision(repo_root, 104, "draft", supersedes="D105")
    _decision(repo_root, 105, "deprecated")

    findings = _cite4(citation_checker.check(repo_root))

    assert len(_for_file(findings, "specs/decisions/D100.md")) >= 1, findings
    d101 = _for_file(findings, "specs/decisions/D101.md")
    assert len(d101) >= 1, findings
    assert any("D102" in (_get(f, "message") or "") for f in d101), d101
    assert len(_for_file(findings, "specs/decisions/D103.md")) >= 1, findings
    assert _for_file(findings, "specs/decisions/D104.md") == [], findings
    assert _for_file(findings, "specs/decisions/D105.md") == [], findings

    for f in findings:
        _check_shape(f)

    files_in_order = [_norm(_get(f, "file")) for f in findings]
    assert files_in_order == sorted(files_in_order), files_in_order