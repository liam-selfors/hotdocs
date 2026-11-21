# hotdocs-criterion: sha256:882e46402efa4f7fd90108c83c2d1ef28d569b0aca00590b05789ee71d2dc536
"""AC-LINT-017: a guarantee file whose heading differs from its filename stem
yields a fail-severity finding for rule R-LINT-017."""

import spec_linter

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def severity_of(finding):
    sev = field(finding, "severity")
    return getattr(sev, "value", sev)


PRODUCT = (
    "---\n"
    "id: P-FOO\n"
    "title: Foo works\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Foo works\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A foo can be made.\n"
    "\n"
    "### CS-FOO-001\n"
    "Covers: P-FOO\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given nothing\n"
    "When a foo is made\n"
    "Then it exists\n"
    "```\n"
)

COMPONENT = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "realizes: [P-FOO]\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Makes a foo.\n"
    "\n"
    "## Scope\n"
    "\n"
    "**In scope:** making a foo. **Out of scope:** everything else.\n"
    "\n"
    "## Definitions\n"
    "\n"
    "No deltas from `specs/glossary.md`.\n"
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
    "None.\n"
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
    "None.\n"
    "\n"
    "## Change log\n"
    "\n"
    "- Initial draft.\n"
)

REQUIREMENT = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `make_foo()` MUST return the string `\"foo\"`.\n"
)

LIBRARY = (
    "# Library\n"
    "\n"
    "One module file, `foo.py`.\n"
    "\n"
    "```\n"
    "make_foo() -> str\n"
    "```\n"
)

ACCEPTANCE = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given nothing\n"
    "When make_foo() is called\n"
    "Then the result is \"foo\"\n"
    "```\n"
)

CONSTRAINTS = (
    "# Foo \u2014 Non-Functional Constraints\n"
    "\n"
    "- **Pure.** No I/O.\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_clean_corpus(repo_root):
    write(repo_root / "specs" / "product" / "foo.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    write(comp / "constraints.md", CONSTRAINTS)
    return comp


def guarantee_text(heading_id):
    return (
        "# " + heading_id + "\n"
        "\n"
        "**" + heading_id + "** \u2014 `make_foo()` MUST have no side effects.\n"
    )


def r_lint_017_findings(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-017"]


def test_clean_corpus_has_no_hard_failures(tmp_path):
    repo_root = tmp_path / "repo"
    build_clean_corpus(repo_root)
    report = spec_linter.lint(None, repo_root)
    assert field(report, "hard_failures") == 0


def test_matching_guarantee_heading_gives_no_r_lint_017_finding(tmp_path):
    repo_root = tmp_path / "repo"
    comp = build_clean_corpus(repo_root)
    write(comp / "interface" / "guarantees" / "G-FOO-001.md", guarantee_text("G-FOO-001"))
    report = spec_linter.lint(None, repo_root)
    assert [f for f in r_lint_017_findings(report) if severity_of(f) == "fail"] == []


def test_guarantee_heading_mismatch_fails_r_lint_017(tmp_path):
    repo_root = tmp_path / "repo"
    comp = build_clean_corpus(repo_root)
    write(comp / "interface" / "guarantees" / "G-FOO-001.md", guarantee_text("G-FOO-002"))

    report = spec_linter.lint(None, repo_root)

    fails = [f for f in r_lint_017_findings(report) if severity_of(f) == "fail"]
    assert fails, "expected a fail-severity R-LINT-017 finding, got: " + repr(
        field(report, "findings")
    )
    assert field(report, "hard_failures") >= 1