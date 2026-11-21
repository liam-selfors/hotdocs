# hotdocs-criterion: sha256:a0fe9c20b55b3b2bb2b0c15d2c990e9752037a610ddd24678867a429eb33af0f
"""AC-CITE-004: supersedes / status: deprecated consistency (R-CITE-004)."""

from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _decision(repo_root, n, status, supersedes=None):
    lines = [
        "---",
        "id: D" + str(n),
        "title: Decision " + str(n),
        "status: " + status,
        "owners: [team-a]",
    ]
    if status == "ratified":
        lines.append("last_ratified_commit: 0000000")
    if supersedes is not None:
        lines.append("supersedes: " + supersedes)
    lines.append("---")
    lines.append("")
    lines.append("# Decision " + str(n))
    lines.append("")
    lines.append("A plain decision body with no citations.")
    lines.append("")
    path = repo_root / "specs" / "decisions" / ("D" + str(n) + ".md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def _base(repo_root):
    specs = repo_root / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    (specs / "glossary.md").write_text(
        "# Glossary\n\n- **Example term** — an example entry.\n"
    )


def _cite4(findings):
    out = []
    for f in findings:
        if field(f, "rule_id") == "R-CITE-004":
            out.append(f)
    return out


def _for_file(findings, rel):
    return [f for f in findings if field(f, "file") == rel]


def _check_shape(findings):
    for f in findings:
        assert field(f, "severity") in ("fail", "warn")
        assert isinstance(field(f, "line"), int)
        assert isinstance(field(f, "message"), str)


def test_supersedes_nonexistent_decision_is_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    _base(repo_root)
    _decision(repo_root, 101, "ratified", supersedes="D150")

    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)
    cite4 = _cite4(findings)
    _check_shape(cite4)

    hits = _for_file(cite4, "specs/decisions/D101.md")
    assert hits, "expected an R-CITE-004 finding on D101.md, got " + repr(findings)


def test_supersedes_still_ratified_decision_is_flagged_naming_it(tmp_path):
    repo_root = tmp_path / "repo"
    _base(repo_root)
    _decision(repo_root, 102, "ratified", supersedes="D103")
    _decision(repo_root, 103, "ratified")

    findings = citation_checker.check(repo_root)
    cite4 = _cite4(findings)
    _check_shape(cite4)

    hits = _for_file(cite4, "specs/decisions/D102.md")
    assert hits, "expected an R-CITE-004 finding on D102.md, got " + repr(findings)
    assert any("D103" in field(f, "message") for f in hits), repr(hits)


def test_orphan_deprecated_decision_is_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    _base(repo_root)
    # Orphan: deprecated, but nothing supersedes it.
    _decision(repo_root, 104, "deprecated")
    # Control: a consistent supersedes/deprecated pair.
    _decision(repo_root, 105, "ratified", supersedes="D106")
    _decision(repo_root, 106, "deprecated")

    findings = citation_checker.check(repo_root)
    cite4 = _cite4(findings)
    _check_shape(cite4)

    hits = _for_file(cite4, "specs/decisions/D104.md")
    assert hits, "expected an R-CITE-004 finding on D104.md, got " + repr(findings)

    assert not _for_file(cite4, "specs/decisions/D105.md"), repr(cite4)
    assert not _for_file(cite4, "specs/decisions/D106.md"), repr(cite4)