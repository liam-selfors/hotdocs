# hotdocs-criterion: sha256:25a1f40a4658e71df5b4c984eb1eece22b0351feab9f0f3cb12edc399bfee7d9
import spec_linter

from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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

COMPONENT_HEAD = (
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
)

COMPONENT_TAIL = (
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


def build_corpus(repo_root, purpose_text, rationale_text=None):
    write(repo_root / "specs" / "product" / "foo.md", PRODUCT)
    component = COMPONENT_HEAD + "## Purpose\n\n" + purpose_text + "\n\n"
    if rationale_text is not None:
        component += "## Rationale\n\n" + rationale_text + "\n\n"
    component += COMPONENT_TAIL
    comp_dir = repo_root / "specs" / "components" / "foo"
    write(comp_dir / "component.md", component)
    write(comp_dir / "requirements" / "R-FOO-001.md", REQUIREMENT)
    write(comp_dir / "interface" / "library.md", LIBRARY)
    write(comp_dir / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    write(comp_dir / "constraints.md", CONSTRAINTS)


def lint_024_findings(report):
    return [
        f for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-024"
    ]


CITATIONS = [
    "extracted once D30 found a real coupling",
    "extracted once `D30` found a real coupling",
]


@pytest.mark.parametrize("citation", CITATIONS)
def test_purpose_with_decision_citation_fails(tmp_path, citation):
    repo_root = tmp_path / "repo"
    build_corpus(repo_root, "Makes a foo, " + citation + ".")

    report = spec_linter.lint(None, repo_root)
    findings = lint_024_findings(report)

    assert findings, "expected an R-LINT-024 finding for a Purpose citing D30"
    assert all(field(f, "severity") == "fail" for f in findings)
    assert any(
        str(field(f, "file")).replace("\\", "/").endswith(
            "specs/components/foo/component.md"
        )
        for f in findings
    )
    assert field(report, "hard_failures") >= 1

    code = spec_linter.main(["--repo-root=" + str(repo_root)])
    assert code == 1


@pytest.mark.parametrize("citation", CITATIONS)
def test_citation_moved_to_rationale_has_no_lint_024(tmp_path, citation):
    repo_root = tmp_path / "repo"
    build_corpus(
        repo_root,
        "Makes a foo.",
        rationale_text="This component was " + citation + ".",
    )

    report = spec_linter.lint(None, repo_root)
    findings = lint_024_findings(report)

    assert findings == [], (
        "expected no R-LINT-024 finding when the citation lives in Rationale, got "
        + repr(findings)
    )