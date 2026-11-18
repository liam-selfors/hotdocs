# hotdocs-criterion: sha256:b29a77c78500833d6dcc280fb72cfda290f3e997d14a7cdb7e88a650165b1557
"""AC-LINT-017: a guarantee file whose own heading disagrees with its
filename's stem yields a fail-severity R-LINT-017 finding."""

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
    "owners: [pipeline-team]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does a small, well-defined thing for its dependents.\n"
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

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — The component MUST return its results sorted.\n"
)

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given an unsorted input\n"
    "When foo runs\n"
    "Then the results are sorted\n"
    "```\n"
)

CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "None.\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Foo thing** — a small thing foo does.\n"
)


def build_corpus(repo_root: Path, guarantee_heading: str) -> Path:
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface" / "guarantees").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)
    (comp / "constraints.md").write_text(CONSTRAINTS_MD)
    guarantee = comp / "interface" / "guarantees" / "G-FOO-001.md"
    guarantee.write_text(
        "# " + guarantee_heading + "\n"
        "\n"
        "Results returned by foo MUST be in sorted order.\n"
    )
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_MD)
    return guarantee


def lint017_fails(report):
    findings = field(report, "findings")
    return [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-017" and field(f, "severity") == "fail"
    ]


def test_mismatched_guarantee_heading_yields_fail_finding(tmp_path):
    build_corpus(tmp_path, "G-FOO-002")

    report = spec_linter.lint(None, tmp_path)

    hits = lint017_fails(report)
    assert hits, (
        "expected a fail-severity R-LINT-017 finding, got: "
        + repr(
            [
                (field(f, "rule_id"), field(f, "severity"), field(f, "message"))
                for f in field(report, "findings")
            ]
        )
    )
    assert field(report, "hard_failures") >= 1
    assert any("G-FOO-001" in str(field(f, "file")) for f in hits)


def test_matching_guarantee_heading_yields_no_r_lint_017_fail(tmp_path):
    build_corpus(tmp_path, "G-FOO-001")

    report = spec_linter.lint(None, tmp_path)

    assert lint017_fails(report) == []


def test_cli_reports_r_lint_017_and_exits_1(tmp_path, capsys):
    build_corpus(tmp_path, "G-FOO-002")

    code = spec_linter.main(["--format=json", "--repo-root=" + str(tmp_path)])

    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    assert any(
        f["rule_id"] == "R-LINT-017" and f["severity"] == "fail"
        for f in doc["findings"]
    )