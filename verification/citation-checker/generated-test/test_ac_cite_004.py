"""AC-CITE-004 (Covers: R-CITE-004): supersedes / status: deprecated consistency."""

import citation_checker

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _decision(doc_id, status, supersedes=None):
    lines = [
        "---",
        f"id: {doc_id}",
        f'title: "Decision {doc_id}"',
        f"status: {status}",
        "owners: [spec-team]",
    ]
    if status == "ratified":
        lines.append("last_ratified_commit: 0000000000000000000000000000000000000000")
    if supersedes is not None:
        lines.append(f"supersedes: {supersedes}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {doc_id}")
    lines.append("")
    lines.append("A synthetic decision record used as a test fixture.")
    lines.append("")
    return "\n".join(lines)


def _base_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only by this fixture.\n",
    )
    comp = repo_root / "specs" / "components" / "dummy"
    _write(
        comp / "component.md",
        "\n".join(
            [
                "---",
                "id: comp-dummy",
                'title: "Dummy"',
                "status: draft",
                "owners: [spec-team]",
                "sealed: true",
                "source_path: legacy/dummy/",
                "---",
                "",
                "# Dummy",
                "",
                "## Purpose",
                "",
                "A fixture component.",
                "",
                "## Scope",
                "",
                "- In scope: nothing.",
                "",
                "## Definitions",
                "",
                "None.",
                "",
                "## Behavior",
                "",
                "See `requirements/`.",
                "",
                "## Interfaces",
                "",
                "See `interface/`.",
                "",
                "## Data",
                "",
                "See `interface/data/`.",
                "",
                "## Acceptance criteria",
                "",
                "See `acceptance/`.",
                "",
                "## Non-functional constraints",
                "",
                "See `constraints.md`.",
                "",
                "## Open questions",
                "",
                "## Change log",
                "",
                "- Created.",
                "",
            ]
        ),
    )
    _write(
        comp / "requirements" / "R-DUMMY-001.md",
        "# R-DUMMY-001\n\n**R-DUMMY-001** — the dummy MUST exist.\n",
    )
    _write(
        comp / "acceptance" / "AC-DUMMY-001.md",
        "# AC-DUMMY-001\n\nCovers: R-DUMMY-001\nKind: compiled\n\n"
        "```gherkin\nGiven nothing\nWhen nothing\nThen nothing\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def _build_repo(tmp_path: Path, decisions) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _base_corpus(repo_root)
    # Control decisions, always valid: D104 fully replaces deprecated D105;
    # D120 supersedes the exempt, never-formalized D5.
    all_decisions = {
        "D104": ("ratified", "D105"),
        "D105": ("deprecated", None),
        "D120": ("ratified", "D5"),
    }
    all_decisions.update(decisions)
    for doc_id, (status, supersedes) in all_decisions.items():
        _write(
            repo_root / "specs" / "decisions" / f"{doc_id}.md",
            _decision(doc_id, status, supersedes),
        )
    return repo_root


def _norm(p) -> str:
    return str(p).replace("\\", "/")


def _cite4(findings):
    out = []
    for f in findings:
        assert set(f.keys() if isinstance(f, dict) else vars(f).keys()) >= {
            "rule_id",
            "severity",
            "file",
            "line",
            "message",
        }
        if field(f, "rule_id") == "R-CITE-004":
            out.append(f)
    for f in out:
        assert field(f, "severity") in ("fail", "warn")
        assert isinstance(field(f, "line"), int)
        assert isinstance(field(f, "message"), str)
    return out


def _for_file(findings, rel):
    return [f for f in findings if _norm(field(f, "file")) == rel]


def _assert_controls_clean(findings):
    for rel in (
        "specs/decisions/D104.md",
        "specs/decisions/D105.md",
        "specs/decisions/D120.md",
    ):
        assert _for_file(findings, rel) == [], (
            f"unexpected R-CITE-004 finding for valid control {rel}: "
            f"{_for_file(findings, rel)}"
        )


def test_controls_alone_produce_no_r_cite_004(tmp_path):
    repo_root = _build_repo(tmp_path, {})
    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)
    assert _cite4(findings) == []


def test_supersedes_nonexistent_decision_is_flagged(tmp_path):
    repo_root = _build_repo(tmp_path, {"D100": ("ratified", "D200")})
    findings = _cite4(citation_checker.check(repo_root))
    hits = _for_file(findings, "specs/decisions/D100.md")
    assert hits, f"expected an R-CITE-004 finding on D100.md, got {findings}"
    _assert_controls_clean(findings)


def test_supersedes_still_ratified_decision_is_flagged_naming_it(tmp_path):
    repo_root = _build_repo(
        tmp_path,
        {
            "D101": ("ratified", "D102"),
            "D102": ("ratified", None),
        },
    )
    findings = _cite4(citation_checker.check(repo_root))
    hits = _for_file(findings, "specs/decisions/D101.md")
    assert hits, f"expected an R-CITE-004 finding on D101.md, got {findings}"
    assert any("D102" in field(f, "message") for f in hits), (
        f"expected the D101.md finding to name D102, got {hits}"
    )
    _assert_controls_clean(findings)


def test_deprecated_decision_not_superseded_by_anyone_is_flagged(tmp_path):
    repo_root = _build_repo(tmp_path, {"D103": ("deprecated", None)})
    findings = _cite4(citation_checker.check(repo_root))
    hits = _for_file(findings, "specs/decisions/D103.md")
    assert hits, f"expected an R-CITE-004 finding on D103.md, got {findings}"
    _assert_controls_clean(findings)


def test_all_three_violations_together(tmp_path):
    repo_root = _build_repo(
        tmp_path,
        {
            "D100": ("ratified", "D200"),
            "D101": ("ratified", "D102"),
            "D102": ("ratified", None),
            "D103": ("deprecated", None),
        },
    )
    findings = _cite4(citation_checker.check(repo_root))
    assert _for_file(findings, "specs/decisions/D100.md")
    d101 = _for_file(findings, "specs/decisions/D101.md")
    assert d101 and any("D102" in field(f, "message") for f in d101)
    assert _for_file(findings, "specs/decisions/D103.md")
    _assert_controls_clean(findings)