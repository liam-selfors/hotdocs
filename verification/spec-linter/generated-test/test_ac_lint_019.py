# hotdocs-criterion: sha256:34701952ae252aa7d8e64885505487f9b733d0c6213ae6e6562646e2cee89456
"""AC-LINT-019: a spec line ending in two trailing spaces yields a
fail-severity R-LINT-019 finding naming that line."""

import spec_linter

from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FENCE = "```"

PRODUCT_FOO = "\n".join([
    "---",
    "id: P-FOO",
    "title: Foo works",
    "status: draft",
    "owners: [team-a]",
    "---",
    "",
    "# Foo works",
    "",
    "## Purpose",
    "",
    "A foo can be made.",
    "",
    "### CS-FOO-001",
    "Covers: P-FOO",
    "Kind: generated-test",
    "",
    FENCE + "gherkin",
    "Given nothing",
    "When a foo is made",
    "Then it exists",
    FENCE,
    "",
])

COMPONENT_MD_LINES = [
    "---",
    "id: comp-foo",
    "title: Foo",
    "status: draft",
    "owners: [team-a]",
    "depends_on: []",
    "realizes: [P-FOO]",
    "sealed: false",
    "---",
    "",
    "# Foo",
    "",
    "## Purpose",
    "",
    "Makes a foo.",
    "",
    "## Scope",
    "",
    "**In scope:** making a foo. **Out of scope:** everything else.",
    "",
    "## Definitions",
    "",
    "No deltas from `specs/glossary.md`.",
    "",
    "## Behavior",
    "",
    "See `requirements/`.",
    "",
    "## Interfaces",
    "",
    "See `interface/`.",
    "",
    "## Data",
    "",
    "None.",
    "",
    "## Acceptance criteria",
    "",
    "See `acceptance/`.",
    "",
    "## Non-functional constraints",
    "",
    "See `constraints.md`.",
    "",
    "## Open questions",
    "",
    "None.",
    "",
    "## Change log",
    "",
    "- Initial draft.",
]

REQUIREMENT = "\n".join([
    "# R-FOO-001",
    "",
    '**R-FOO-001** \u2014 `make_foo()` MUST return the string `"foo"`.',
    "",
])

LIBRARY = "\n".join([
    "# Library",
    "",
    "One module file, `foo.py`.",
    "",
    FENCE,
    "make_foo() -> str",
    FENCE,
    "",
])

ACCEPTANCE = "\n".join([
    "# AC-FOO-001",
    "",
    "Covers: R-FOO-001",
    "Kind: generated-test",
    "",
    FENCE + "gherkin",
    "Given nothing",
    "When make_foo() is called",
    'Then the result is "foo"',
    FENCE,
    "",
])

CONSTRAINTS_LINES = [
    "# Foo \u2014 Non-Functional Constraints",
    "",
    "- **Pure.** No I/O.",
]

COMPONENT_REL = "specs/components/foo/component.md"
CONSTRAINTS_REL = "specs/components/foo/constraints.md"


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_clean_corpus(root, component_lines=None, constraints_lines=None):
    write(root, "specs/product/foo.md", PRODUCT_FOO)
    write(root, COMPONENT_REL,
          "\n".join(component_lines or COMPONENT_MD_LINES) + "\n")
    write(root, "specs/components/foo/requirements/R-FOO-001.md", REQUIREMENT)
    write(root, "specs/components/foo/interface/library.md", LIBRARY)
    write(root, "specs/components/foo/acceptance/AC-FOO-001.md", ACCEPTANCE)
    write(root, CONSTRAINTS_REL,
          "\n".join(constraints_lines or CONSTRAINTS_LINES) + "\n")


def lint_findings(root):
    report = spec_linter.lint(None, root)
    return report, list(field(report, "findings"))


def rule_findings(findings, rule_id):
    return [f for f in findings if field(f, "rule_id") == rule_id]


def norm(path_value):
    return str(path_value).replace("\\", "/")


def test_clean_corpus_has_no_trailing_whitespace_finding(tmp_path):
    build_clean_corpus(tmp_path)
    _, findings = lint_findings(tmp_path)
    assert rule_findings(findings, "R-LINT-019") == []


@pytest.mark.parametrize(
    "rel_path,line_number",
    [
        (CONSTRAINTS_REL, 3),   # body line of a unit file
        (COMPONENT_REL, 3),     # a frontmatter line ("title: Foo")
    ],
)
def test_trailing_two_spaces_is_fail_finding_naming_line(
        tmp_path, rel_path, line_number):
    component_lines = list(COMPONENT_MD_LINES)
    constraints_lines = list(CONSTRAINTS_LINES)
    if rel_path == CONSTRAINTS_REL:
        constraints_lines[line_number - 1] += "  "
    else:
        component_lines[line_number - 1] += "  "
    build_clean_corpus(tmp_path, component_lines, constraints_lines)

    # Sanity: exactly one line in the corpus ends in trailing whitespace.
    raw = (tmp_path / rel_path).read_text(encoding="utf-8").splitlines()
    assert raw[line_number - 1].endswith("  ")

    report, findings = lint_findings(tmp_path)
    hits = rule_findings(findings, "R-LINT-019")
    assert len(hits) == 1, findings
    finding = hits[0]
    assert field(finding, "severity") == "fail"
    assert norm(field(finding, "file")).endswith(rel_path)
    assert field(finding, "line") == line_number
    assert field(report, "hard_failures") >= 1

    rc = spec_linter.main(["--repo-root=" + str(tmp_path)])
    assert rc == 1