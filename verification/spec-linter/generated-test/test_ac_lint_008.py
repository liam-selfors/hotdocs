# hotdocs-criterion: sha256:fc8621cc68af2557976001fa737f1a5ae525894b5806c636f8868bb55862908b
import json
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-foo]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does a small, well-defined thing for testing.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the thing.\n"
    "- Out of scope: everything else.\n"
    "\n"
    "## Definitions\n"
    "\n"
    "None.\n"
    "\n"
    "## Behavior\n"
    "\n"
    "See `requirements/`.\n"
    "\n"
    "## Interfaces\n"
    "\n"
    "See `interface/`.\n"
    "\n"
    "## Data\n"
    "\n"
    "See `interface/data/`.\n"
    "\n"
    "## Acceptance criteria\n"
    "\n"
    "See `acceptance/`.\n"
    "\n"
    "## Non-functional constraints\n"
    "\n"
    "See `constraints.md`.\n"
    "\n"
    "## Open questions\n"
    "\n"
    "## Change log\n"
    "\n"
    "- Initial draft.\n"
)

R_FOO_001 = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — Foo MUST return the input unchanged.\n"
)

R_FOO_002 = (
    "# R-FOO-002\n"
    "\n"
    "**R-FOO-002** — Foo MUST reject an empty input.\n"
)

AC_FOO_001 = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-002\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given an empty input\n"
    "When foo runs\n"
    "Then it rejects the input\n"
    "```\n"
)

CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "- Foo SHOULD complete within 1 second, measured by wall clock.\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Foo** — the component under test.\n"
)


def build_fixture(repo_root: Path) -> None:
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(R_FOO_001, encoding="utf-8")
    (comp / "requirements" / "R-FOO-002.md").write_text(R_FOO_002, encoding="utf-8")
    (comp / "acceptance" / "AC-FOO-001.md").write_text(AC_FOO_001, encoding="utf-8")
    (comp / "constraints.md").write_text(CONSTRAINTS_MD, encoding="utf-8")
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_MD, encoding="utf-8")


def names_requirement(finding, req_id):
    message = str(field(finding, "message") or "")
    file = str(field(finding, "file") or "")
    return req_id in message or req_id in file


def lint_008_findings(findings):
    return [f for f in findings if field(f, "rule_id") == "R-LINT-008"]


def test_uncovered_requirement_fails_r_lint_008_library(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    r008 = lint_008_findings(findings)
    matching = [
        f for f in r008
        if field(f, "severity") == "fail" and names_requirement(f, "R-FOO-001")
    ]
    assert matching, (
        "expected a fail-severity R-LINT-008 finding naming R-FOO-001; got "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "file"),
                 field(f, "message")) for f in findings])
    )

    # R-FOO-002 has a covering criterion, so it must not be flagged.
    assert not [f for f in r008 if names_requirement(f, "R-FOO-002")
                and not names_requirement(f, "R-FOO-001")]

    assert field(report, "hard_failures") >= 1


def test_uncovered_requirement_fails_r_lint_008_cli(tmp_path, capsys, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    monkeypatch.chdir(repo_root)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    findings = doc["findings"]
    matching = [
        f for f in findings
        if f["rule_id"] == "R-LINT-008"
        and f["severity"] == "fail"
        and ("R-FOO-001" in str(f.get("message", "")) or "R-FOO-001" in str(f.get("file", "")))
    ]
    assert matching, "expected R-LINT-008 fail finding naming R-FOO-001 in " + repr(findings)
    assert doc["summary"]["hard_failures"] >= 1