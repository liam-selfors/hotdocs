# hotdocs-criterion: sha256:33585dfc56f0892c76ab8e96a7f894fe49c972f7344ce00640df5a61b1c67093
from pathlib import Path

import citation_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def decision(repo_root, num, status, supersedes=None):
    lines = [
        "---",
        "id: D" + str(num),
        "title: Decision " + str(num),
        "status: " + status,
        "owners: [pipeline-team]",
    ]
    if status == "ratified":
        lines.append("last_ratified_commit: 0000000")
    if supersedes is not None:
        lines.append("supersedes: " + supersedes)
    lines.append("---")
    lines.append("")
    lines.append("# Decision " + str(num))
    lines.append("")
    lines.append("A decision about topic number " + str(num) + ".")
    lines.append("")
    write(repo_root / "specs" / "decisions" / ("D" + str(num) + ".md"), "\n".join(lines))


def base_corpus(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a small thing.\n",
    )


def cite_findings(findings, rel_file):
    out = []
    for f in findings:
        if field(f, "rule_id") != "R-CITE-004":
            continue
        if str(field(f, "file")).replace("\\", "/") == rel_file:
            out.append(f)
    return out


def test_supersedes_nonexistent_decision(tmp_path):
    repo_root = tmp_path / "repo"
    base_corpus(repo_root)
    decision(repo_root, 20, "ratified", supersedes="D99")

    findings = citation_checker.check(repo_root)

    hits = cite_findings(findings, "specs/decisions/D20.md")
    assert hits, "expected an R-CITE-004 finding for D20 superseding missing D99; got " + repr(findings)
    for h in hits:
        assert field(h, "severity") in ("fail", "warn")
        assert isinstance(field(h, "line"), int)


def test_supersedes_decision_not_deprecated(tmp_path):
    repo_root = tmp_path / "repo"
    base_corpus(repo_root)
    decision(repo_root, 22, "ratified")
    decision(repo_root, 21, "ratified", supersedes="D22")

    findings = citation_checker.check(repo_root)

    hits = cite_findings(findings, "specs/decisions/D21.md")
    assert hits, "expected an R-CITE-004 finding on superseding record D21; got " + repr(findings)
    assert any("D22" in str(field(h, "message")) for h in hits), (
        "expected the finding to name D22; got " + repr(hits)
    )


def test_deprecated_not_named_by_any_supersedes(tmp_path):
    repo_root = tmp_path / "repo"
    base_corpus(repo_root)
    decision(repo_root, 23, "deprecated")
    # A consistent pair as a control.
    decision(repo_root, 31, "deprecated")
    decision(repo_root, 30, "ratified", supersedes="D31")

    findings = citation_checker.check(repo_root)

    hits = cite_findings(findings, "specs/decisions/D23.md")
    assert hits, "expected an R-CITE-004 finding for orphan deprecated D23; got " + repr(findings)

    assert not cite_findings(findings, "specs/decisions/D31.md"), (
        "D31 is superseded by D30 and should not be flagged; got " + repr(findings)
    )
    assert not cite_findings(findings, "specs/decisions/D30.md"), (
        "D30 supersedes a deprecated D31 and should not be flagged; got " + repr(findings)
    )