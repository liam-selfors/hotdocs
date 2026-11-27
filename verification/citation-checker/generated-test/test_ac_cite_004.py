# hotdocs-criterion: sha256:29ec153fa4780c1176bac4e7bb12de117151e056f17aec87898d86a27534a83a
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _base_corpus(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a small test thing.\n",
    )


def _decision(repo_root, n, status, supersedes=None):
    lines = [
        "---",
        "id: D" + str(n),
        "title: " + "Decision " + str(n),
        "status: " + status,
        "owners: [pipeline-team]",
    ]
    if status == "ratified":
        lines.append("last_ratified_commit: 0000000")
    if supersedes is not None:
        lines.append("supersedes: " + supersedes)
    lines.append("---")
    lines.append("")
    lines.append("# Decision " + str(n))
    lines.append("")
    lines.append("A test decision record covering one topic.")
    lines.append("")
    _write(
        repo_root / "specs" / "decisions" / ("D" + str(n) + ".md"),
        "\n".join(lines),
    )


def _cite4_findings(repo_root):
    findings = citation_checker.check(repo_root)
    out = []
    for f in findings:
        if field(f, "rule_id") == "R-CITE-004":
            out.append(f)
    return out


def _norm(p):
    return str(p).replace("\\", "/")


def _for_file(findings, rel):
    return [f for f in findings if _norm(field(f, "file")) == rel]


def test_supersedes_nonexistent_decision_gets_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _base_corpus(repo_root)
    _decision(repo_root, 100, "ratified", supersedes="D999")

    findings = _cite4_findings(repo_root)
    hits = _for_file(findings, "specs/decisions/D100.md")
    assert hits, "expected an R-CITE-004 finding for D100.md, got: " + repr(findings)
    for f in hits:
        assert isinstance(field(f, "line"), int)
        assert field(f, "severity") in ("fail", "warn")


def test_supersedes_still_ratified_decision_gets_finding_naming_it(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _base_corpus(repo_root)
    _decision(repo_root, 101, "ratified")
    _decision(repo_root, 102, "ratified", supersedes="D101")

    findings = _cite4_findings(repo_root)
    hits = _for_file(findings, "specs/decisions/D102.md")
    assert hits, "expected an R-CITE-004 finding for D102.md, got: " + repr(findings)
    assert any("D101" in str(field(f, "message")) for f in hits), (
        "expected a finding message naming D101, got: " + repr(hits)
    )


def test_deprecated_record_not_superseded_gets_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _base_corpus(repo_root)
    _decision(repo_root, 103, "deprecated")
    _decision(repo_root, 104, "ratified")

    findings = _cite4_findings(repo_root)
    hits = _for_file(findings, "specs/decisions/D103.md")
    assert hits, "expected an R-CITE-004 finding for D103.md, got: " + repr(findings)


def test_consistent_supersession_pair_has_no_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _base_corpus(repo_root)
    _decision(repo_root, 110, "deprecated")
    _decision(repo_root, 111, "ratified", supersedes="D110")

    findings = _cite4_findings(repo_root)
    assert not _for_file(findings, "specs/decisions/D110.md"), repr(findings)
    assert not _for_file(findings, "specs/decisions/D111.md"), repr(findings)