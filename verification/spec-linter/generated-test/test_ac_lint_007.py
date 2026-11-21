# hotdocs-criterion: sha256:ee448cdec6e96d048482fed8a28f6d8c224d8f0bac694f91083b9a41423ae45a
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

COMPONENT_MD = (
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

REQUIREMENT_WITH_KEYWORD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — `make_foo()` MUST return the string `\"foo\"`.\n"
)

REQUIREMENT_WITHOUT_KEYWORD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — `make_foo()` returns the string `\"foo\"`.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "One module file, `foo.py`.\n"
    "\n"
    "```\n"
    "make_foo() -> str\n"
    "```\n"
)

ACCEPTANCE_MD = (
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

CONSTRAINTS_MD = (
    "# Foo — Non-Functional Constraints\n"
    "\n"
    "- **Pure.** No I/O.\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_clean_corpus(repo_root):
    write(repo_root / "specs" / "product" / "foo.md", PRODUCT_FOO)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_WITH_KEYWORD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)


def test_requirement_without_rfc2119_keyword_is_fail_finding_for_r_lint_007(tmp_path):
    repo_root = Path(tmp_path)
    build_clean_corpus(repo_root)

    # Precondition: the clean corpus lints with no hard failures and no
    # R-LINT-007 finding at all.
    clean = spec_linter.lint(None, repo_root)
    assert field(clean, "hard_failures") == 0
    clean_findings = list(field(clean, "findings"))
    assert not [f for f in clean_findings if field(f, "rule_id") == "R-LINT-007"]

    # Given a requirement bullet with no RFC 2119 keyword in its text.
    write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        REQUIREMENT_WITHOUT_KEYWORD,
    )

    # When the linter runs against it.
    report = spec_linter.lint(None, repo_root)

    # Then the report contains a fail-severity finding for rule R-LINT-007.
    findings = list(field(report, "findings"))
    matching = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-007" and field(f, "severity") == "fail"
    ]
    assert matching, "expected a fail-severity R-LINT-007 finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity"), field(f, "message")) for f in findings]
    )
    assert field(report, "hard_failures") >= 1