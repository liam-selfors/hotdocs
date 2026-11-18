# hotdocs-criterion: sha256:e2063970b79ab5544436e2c53c69a0a4a1ed542368cb2505cc8f60cc0072b0f0
"""AC-LINT-010: an acceptance criterion missing a `Kind:` tag is a
fail-severity finding for rule R-LINT-010."""

import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _sev(value):
    sev = field(value, "severity")
    return getattr(sev, "value", sev)


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does one small thing for the test fixture.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the one thing.\n"
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

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 The tool MUST return zero when given no input.\n"
)

CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "- Runs in under one second, measured by timing a single invocation.\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Widget** \u2014 a thing used only by the test fixture.\n"
)


def _acceptance_md(with_kind):
    text = "# AC-FOO-001\n\nCovers: R-FOO-001\n"
    if with_kind:
        text += "Kind: compiled\n"
    text += (
        "\n"
        "```gherkin\n"
        "Given no input\n"
        "When the tool runs\n"
        "Then it returns zero\n"
        "```\n"
    )
    return text


def _build(root, with_kind):
    comp = root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(_acceptance_md(with_kind))
    (comp / "constraints.md").write_text(CONSTRAINTS_MD)
    (root / "specs" / "glossary.md").write_text(GLOSSARY_MD)
    return comp / "acceptance" / "AC-FOO-001.md"


def _lint010(findings):
    return [f for f in findings if field(f, "rule_id") == "R-LINT-010"]


def _is_ac_file(f):
    return str(field(f, "file")).replace("\\", "/").endswith("acceptance/AC-FOO-001.md")


def test_missing_kind_is_fail_finding_for_r_lint_010(tmp_path):
    _build(tmp_path, with_kind=False)

    report = spec_linter.lint(None, tmp_path)
    findings = list(field(report, "findings"))

    hits = [f for f in _lint010(findings) if _is_ac_file(f)]
    assert hits, "expected an R-LINT-010 finding for AC-FOO-001.md, got: " + repr(findings)
    assert any(_sev(f) == "fail" for f in hits), repr(hits)
    assert field(report, "hard_failures") >= 1


def test_criterion_with_kind_has_no_r_lint_010_finding(tmp_path):
    _build(tmp_path, with_kind=True)

    report = spec_linter.lint(None, tmp_path)
    findings = list(field(report, "findings"))

    hits = [f for f in _lint010(findings) if _is_ac_file(f)]
    assert hits == [], repr(hits)


def test_cli_reports_r_lint_010_fail_and_exits_1(tmp_path, capsys):
    _build(tmp_path, with_kind=False)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    hits = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-010"
        and str(f["file"]).replace("\\", "/").endswith("acceptance/AC-FOO-001.md")
    ]
    assert hits, repr(doc)
    assert any(f["severity"] == "fail" for f in hits), repr(hits)
    assert doc["summary"]["hard_failures"] >= 1