"""AC-CITE-004 — covers R-CITE-004.

supersedes / status: deprecated consistency for decision records:
(1) every `supersedes: D<N>` must resolve to a real specs/decisions/D<N>.md;
(2) when it resolves, that record's status must be `deprecated`;
(3) every `status: deprecated` record must be named by at least one other
    real decision's `supersedes` field.
"""

from pathlib import Path

import citation_checker


RULE = "R-CITE-004"


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _decision(repo_root: Path, num: int, status: str, supersedes=None) -> None:
    lines = [
        "---",
        f"id: D{num}",
        f"title: Decision number {num}",
        f"status: {status}",
        "owners: [alice]",
    ]
    if status == "ratified":
        lines.append("last_ratified_commit: 0000000000000000000000000000000000000000")
    if supersedes is not None:
        lines.append(f"supersedes: {supersedes}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Decision number {num}")
    lines.append("")
    lines.append("A synthetic decision record used only as a test fixture.")
    lines.append("")
    _write(repo_root / "specs" / "decisions" / f"D{num}.md", "\n".join(lines))


def _make_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    (repo_root / "specs" / "decisions").mkdir(parents=True, exist_ok=True)
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\nNo entries.\n")
    return repo_root


def _check(repo_root: Path):
    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)
    for f in findings:
        assert _field(f, "rule_id") is not None
        line = _field(f, "line")
        assert isinstance(line, int) and not isinstance(line, bool)
        assert _field(f, "severity") in ("fail", "warn")
        assert isinstance(_field(f, "file"), str)
        assert isinstance(_field(f, "message"), str)
    return findings


def _cite4(findings):
    return [f for f in findings if _field(f, "rule_id") == RULE]


def _files(findings):
    return [str(_field(f, "file")).replace("\\", "/") for f in findings]


def test_supersedes_nonexistent_decision_is_flagged(tmp_path):
    repo_root = _make_repo(tmp_path)
    _decision(repo_root, 1, "ratified", supersedes="D99")

    findings = _cite4(_check(repo_root))

    assert "specs/decisions/D1.md" in _files(findings), findings


def test_supersedes_still_ratified_decision_is_flagged_on_superseding_record(tmp_path):
    repo_root = _make_repo(tmp_path)
    _decision(repo_root, 2, "ratified")
    _decision(repo_root, 3, "ratified", supersedes="D2")

    findings = _cite4(_check(repo_root))

    on_d3 = [f for f in findings if _files([f])[0] == "specs/decisions/D3.md"]
    assert on_d3, findings
    assert any("D2" in str(_field(f, "message")) for f in on_d3), on_d3


def test_deprecated_record_not_named_by_any_supersedes_is_flagged(tmp_path):
    repo_root = _make_repo(tmp_path)
    _decision(repo_root, 4, "deprecated")
    _decision(repo_root, 7, "ratified")

    findings = _cite4(_check(repo_root))
    files = _files(findings)

    assert "specs/decisions/D4.md" in files, findings
    assert "specs/decisions/D7.md" not in files, findings


def test_consistent_supersession_produces_no_finding(tmp_path):
    repo_root = _make_repo(tmp_path)
    _decision(repo_root, 5, "deprecated")
    _decision(repo_root, 6, "ratified", supersedes="D5")
    _decision(repo_root, 8, "ratified")

    findings = _cite4(_check(repo_root))

    assert findings == [], findings


def test_mixed_corpus_flags_exactly_the_inconsistent_records_in_path_order(tmp_path):
    repo_root = _make_repo(tmp_path)
    # (1) dangling supersedes
    _decision(repo_root, 1, "ratified", supersedes="D99")
    # (2) supersedes a still-ratified record
    _decision(repo_root, 2, "ratified")
    _decision(repo_root, 3, "ratified", supersedes="D2")
    # (3) deprecated with nobody superseding it
    _decision(repo_root, 4, "deprecated")
    # consistent pair
    _decision(repo_root, 5, "deprecated")
    _decision(repo_root, 6, "ratified", supersedes="D5")

    findings = _cite4(_check(repo_root))
    files = _files(findings)

    assert "specs/decisions/D1.md" in files, findings
    assert "specs/decisions/D3.md" in files, findings
    assert "specs/decisions/D4.md" in files, findings
    assert "specs/decisions/D5.md" not in files, findings
    assert "specs/decisions/D6.md" not in files, findings

    d3 = [f for f in findings if _files([f])[0] == "specs/decisions/D3.md"]
    assert any("D2" in str(_field(f, "message")) for f in d3), d3

    assert files == sorted(files), files