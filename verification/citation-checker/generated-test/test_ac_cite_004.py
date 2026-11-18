# hotdocs-criterion: sha256:d6749cf7275d3b90c9f9bae84a3e29c995ffae1e78138a13882d6f1a1b5c5d0a
import citation_checker

from pathlib import Path


RULE = "R-CITE-004"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_decision(repo_root, number, status, supersedes=None):
    decisions = Path(repo_root) / "specs" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    did = "D" + str(number)
    lines = [
        "---",
        "id: " + did,
        "title: Decision number " + str(number),
        "status: " + status,
        "owners: [team-a]",
    ]
    if status == "ratified":
        lines.append("last_ratified_commit: 0000000")
    if supersedes is not None:
        lines.append("supersedes: " + supersedes)
    lines.append("---")
    lines.append("")
    lines.append("# Decision " + str(number))
    lines.append("")
    lines.append("A plain decision body with no citations in it.")
    lines.append("")
    (decisions / (did + ".md")).write_text("\n".join(lines), encoding="utf-8")


def make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    specs = repo_root / "specs"
    (specs / "decisions").mkdir(parents=True)
    (specs / "glossary.md").write_text("# Glossary\n", encoding="utf-8")
    return repo_root


def cite4_findings(repo_root):
    findings = citation_checker.check(repo_root)
    assert isinstance(findings, list)
    return [f for f in findings if field(f, "rule_id") == RULE]


def check_shape(finding):
    assert field(finding, "severity") in ("fail", "warn")
    assert isinstance(field(finding, "line"), int)
    assert isinstance(field(finding, "message"), str)


def files_of(findings):
    return [field(f, "file") for f in findings]


def test_supersedes_nonexistent_decision_gets_finding(tmp_path):
    repo_root = make_repo(tmp_path)
    write_decision(repo_root, 100, "ratified", supersedes="D150")

    findings = cite4_findings(repo_root)

    on_record = [f for f in findings if field(f, "file") == "specs/decisions/D100.md"]
    assert len(on_record) >= 1, findings
    for f in on_record:
        check_shape(f)


def test_supersedes_existing_but_not_deprecated_gets_finding_naming_target(tmp_path):
    repo_root = make_repo(tmp_path)
    write_decision(repo_root, 101, "ratified", supersedes="D102")
    write_decision(repo_root, 102, "ratified")

    findings = cite4_findings(repo_root)

    on_record = [f for f in findings if field(f, "file") == "specs/decisions/D101.md"]
    assert len(on_record) >= 1, findings
    assert any("D102" in field(f, "message") for f in on_record), on_record
    for f in on_record:
        check_shape(f)
    # The still-ratified target is not deprecated, so the inverse rule
    # does not apply to it.
    assert "specs/decisions/D102.md" not in files_of(findings), findings


def test_deprecated_record_never_superseded_gets_finding(tmp_path):
    repo_root = make_repo(tmp_path)
    write_decision(repo_root, 103, "deprecated")
    write_decision(repo_root, 104, "ratified")

    findings = cite4_findings(repo_root)

    on_record = [f for f in findings if field(f, "file") == "specs/decisions/D103.md"]
    assert len(on_record) >= 1, findings
    for f in on_record:
        check_shape(f)
    assert "specs/decisions/D104.md" not in files_of(findings), findings


def test_consistent_supersession_has_no_finding(tmp_path):
    repo_root = make_repo(tmp_path)
    write_decision(repo_root, 110, "ratified", supersedes="D111")
    write_decision(repo_root, 111, "deprecated")

    findings = cite4_findings(repo_root)

    assert findings == [], findings


def test_all_three_cases_together_each_flagged(tmp_path):
    repo_root = make_repo(tmp_path)
    write_decision(repo_root, 100, "ratified", supersedes="D150")
    write_decision(repo_root, 101, "ratified", supersedes="D102")
    write_decision(repo_root, 102, "ratified")
    write_decision(repo_root, 103, "deprecated")
    write_decision(repo_root, 110, "ratified", supersedes="D111")
    write_decision(repo_root, 111, "deprecated")

    findings = cite4_findings(repo_root)
    files = files_of(findings)

    assert "specs/decisions/D100.md" in files, findings
    assert "specs/decisions/D101.md" in files, findings
    assert "specs/decisions/D103.md" in files, findings
    assert "specs/decisions/D102.md" not in files, findings
    assert "specs/decisions/D110.md" not in files, findings
    assert "specs/decisions/D111.md" not in files, findings
    d101 = [f for f in findings if field(f, "file") == "specs/decisions/D101.md"]
    assert any("D102" in field(f, "message") for f in d101), d101
    for f in findings:
        check_shape(f)