from pathlib import Path

import citation_checker


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _decision(doc_id: str, builds_on: list) -> str:
    lines = [
        "---",
        f"id: {doc_id}",
        f"title: Decision {doc_id}",
        "status: draft",
        "owners: [alice]",
    ]
    if builds_on is not None:
        lines.append("builds_on: [" + ", ".join(builds_on) + "]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {doc_id}")
    lines.append("")
    lines.append("A synthetic decision record used only as a test fixture.")
    lines.append("")
    return "\n".join(lines)


def _make_repo(root: Path, decisions: dict) -> Path:
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )
    for doc_id, builds_on in decisions.items():
        _write(root / "specs" / "decisions" / f"{doc_id}.md", _decision(doc_id, builds_on))
    return root


def _cite005(findings):
    assert isinstance(findings, list)
    return [f for f in findings if _get(f, "rule_id") == "R-CITE-005"]


def test_only_unresolved_builds_on_gets_finding_and_d7_is_exempt(tmp_path):
    repo_root = _make_repo(
        tmp_path / "repo",
        {
            # builds_on names a decision number with no specs/decisions/ file
            "D100": ["D555"],
            # builds_on names D7, one of D1-D14, never formalized as a file
            "D101": ["D7"],
            # control: builds_on resolves to a real file
            "D102": ["D100"],
        },
    )

    findings = citation_checker.check(repo_root)
    cite = _cite005(findings)

    assert len(cite) == 1, f"expected exactly one R-CITE-005 finding, got {findings!r}"
    finding = cite[0]
    assert _get(finding, "file") == "specs/decisions/D100.md"
    assert _get(finding, "severity") in ("fail", "warn")
    line = _get(finding, "line")
    assert isinstance(line, int) and not isinstance(line, bool)
    assert line >= 1
    message = _get(finding, "message")
    assert isinstance(message, str) and message

    files = [_get(f, "file") for f in cite]
    assert "specs/decisions/D101.md" not in files
    assert "specs/decisions/D102.md" not in files


def test_d1_and_d14_exempt_but_d15_is_not(tmp_path):
    repo_root = _make_repo(
        tmp_path / "repo",
        {
            "D100": ["D1"],
            "D101": ["D14"],
            "D102": ["D15"],
        },
    )

    findings = citation_checker.check(repo_root)
    cite = _cite005(findings)

    files = [_get(f, "file") for f in cite]
    assert files == ["specs/decisions/D102.md"], f"unexpected R-CITE-005 findings: {findings!r}"


def test_no_findings_when_all_builds_on_resolve_or_exempt(tmp_path):
    repo_root = _make_repo(
        tmp_path / "repo",
        {
            "D100": ["D7"],
            "D101": ["D100"],
            "D102": None,
        },
    )

    findings = citation_checker.check(repo_root)
    assert _cite005(findings) == []