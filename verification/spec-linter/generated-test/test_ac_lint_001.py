# hotdocs-criterion: sha256:e86b5860913cf6e5dec89edf7d9ece7b142c0804c0d78aac6c2269db17797ef5
"""AC-LINT-001: a component.md with no `owners` field in its frontmatter
yields a fail-severity finding for rule R-LINT-001."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRODUCT_FOO = (
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

COMPONENT_BODY = (
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


def component_md(with_owners):
    lines = [
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
    ]
    if with_owners:
        lines.append("owners: [team-a]")
    lines += [
        "depends_on: []",
        "realizes: [P-FOO]",
        "sealed: false",
        "---",
    ]
    return "\n".join(lines) + "\n" + COMPONENT_BODY


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


def build_corpus(repo_root, with_owners):
    specs = repo_root / "specs"
    write(specs / "product" / "foo.md", PRODUCT_FOO)
    comp = specs / "components" / "foo"
    write(comp / "component.md", component_md(with_owners))
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    write(comp / "constraints.md", CONSTRAINTS)


def test_clean_corpus_has_no_hard_failures(tmp_path):
    repo_root = tmp_path / "clean"
    build_corpus(repo_root, with_owners=True)
    report = spec_linter.lint(None, repo_root)
    assert field(report, "hard_failures") == 0
    r001 = [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-001"]
    assert r001 == []


def test_missing_owners_reports_fail_for_r_lint_001(tmp_path):
    repo_root = tmp_path / "missing-owners"
    build_corpus(repo_root, with_owners=False)

    text = (repo_root / "specs" / "components" / "foo" / "component.md").read_text(encoding="utf-8")
    frontmatter = text.split("---")[1]
    assert "owners" not in frontmatter

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    matching = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-001" and field(f, "severity") == "fail"
    ]
    assert matching, "expected a fail-severity R-LINT-001 finding, got: " + repr(findings)
    assert field(report, "hard_failures") >= 1