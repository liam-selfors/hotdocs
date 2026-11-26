# hotdocs-criterion: sha256:baf9746edfcf412471c4fee3084420becef52309f9fbd79ae45d050526800646
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [test-team]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does a small thing for tests.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the small thing.\n"
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

REQ_001 = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — Foo MUST do the first thing.\n"
)

REQ_002 = (
    "# R-FOO-002\n"
    "\n"
    "**R-FOO-002** — Foo MUST do the second thing.\n"
)

AC_001 = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-002\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a foo\n"
    "When it runs\n"
    "Then it does the second thing\n"
    "```\n"
)

CONSTRAINTS = (
    "# Constraints\n"
    "\n"
    "- None measurable; measured by inspection.\n"
)

GLOSSARY = (
    "# Glossary\n"
    "\n"
    "- **Foo** — a test component.\n"
)


def build_fixture(repo_root: Path) -> None:
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(REQ_001)
    (comp / "requirements" / "R-FOO-002.md").write_text(REQ_002)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(AC_001)
    (comp / "constraints.md").write_text(CONSTRAINTS)
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY)


def names(finding, req_id):
    message = field(finding, "message") or ""
    file = field(finding, "file") or ""
    return req_id in str(message) or req_id in str(file)


def lint_008_findings(findings):
    return [f for f in findings if field(f, "rule_id") == "R-LINT-008"]


def test_uncovered_requirement_fails_forward_traceability(tmp_path):
    build_fixture(tmp_path)

    report = spec_linter.lint(None, tmp_path)
    findings = list(field(report, "findings"))
    r008 = lint_008_findings(findings)

    matching = [
        f for f in r008
        if names(f, "R-FOO-001") and field(f, "severity") == "fail"
    ]
    assert matching, "expected a fail R-LINT-008 finding naming R-FOO-001, got: " + repr(findings)

    # The covered requirement must not be flagged by R-LINT-008.
    assert not [f for f in r008 if names(f, "R-FOO-002")], repr(r008)

    assert field(report, "hard_failures") >= 1


def test_uncovered_requirement_cli_json_exit_1(tmp_path, capsys):
    build_fixture(tmp_path)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    r008 = [f for f in doc["findings"] if f["rule_id"] == "R-LINT-008"]
    assert any(
        f["severity"] == "fail"
        and ("R-FOO-001" in f.get("message", "") or "R-FOO-001" in f.get("file", ""))
        for f in r008
    ), repr(doc)
    assert doc["summary"]["hard_failures"] >= 1