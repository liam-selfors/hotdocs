# hotdocs-criterion: sha256:5054cc8b4ec253fa97f8a952377056dd10dd6cef07f17195090c08b87817eb39
import json
from pathlib import Path

import pytest

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

CLEAN_FRONTMATTER_LINES = [
    "id: comp-foo",
    "title: Foo",
    "status: draft",
    "owners: [team-a]",
    "depends_on: []",
    "realizes: [P-FOO]",
    "sealed: false",
]

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


def component_md(frontmatter_lines):
    return "---\n" + "\n".join(frontmatter_lines) + "\n---\n" + COMPONENT_BODY


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_clean_corpus(repo_root):
    write(repo_root / "specs" / "product" / "foo.md", PRODUCT_FOO)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", component_md(CLEAN_FRONTMATTER_LINES))
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    write(comp / "constraints.md", CONSTRAINTS)
    return comp / "component.md"


VARIANTS = {
    "sealed-false-empty-realizes": [
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [team-a]",
        "depends_on: []",
        "realizes: []",
        "sealed: false",
    ],
    "sealed-false-no-realizes-key": [
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [team-a]",
        "depends_on: []",
        "sealed: false",
    ],
    "sealed-absent-empty-realizes": [
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [team-a]",
        "depends_on: []",
        "realizes: []",
    ],
    "sealed-absent-no-realizes-key": [
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [team-a]",
        "depends_on: []",
    ],
}


def r_lint_006_fails(findings):
    return [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-006" and field(f, "severity") == "fail"
    ]


def test_clean_corpus_has_no_r_lint_006(tmp_path):
    repo_root = tmp_path / "repo"
    build_clean_corpus(repo_root)
    report = spec_linter.lint(None, repo_root)
    assert field(report, "hard_failures") == 0
    assert r_lint_006_fails(field(report, "findings")) == []


@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_non_sealed_component_without_realizes_fails(tmp_path, variant):
    repo_root = tmp_path / "repo"
    component_path = build_clean_corpus(repo_root)

    # Precondition: the clean corpus lints with no hard failures.
    assert field(spec_linter.lint(None, repo_root), "hard_failures") == 0

    write(component_path, component_md(VARIANTS[variant]))

    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    matches = r_lint_006_fails(findings)
    assert matches, "expected a fail-severity R-LINT-006 finding, got: " + repr(findings)
    assert any(
        str(field(f, "file")).replace("\\", "/").endswith("specs/components/foo/component.md")
        for f in matches
    ), repr(matches)
    assert field(report, "hard_failures") >= 1


def test_cli_reports_r_lint_006_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    component_path = build_clean_corpus(repo_root)
    write(component_path, component_md(VARIANTS["sealed-false-empty-realizes"]))

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    matches = [
        f
        for f in data["findings"]
        if f["rule_id"] == "R-LINT-006" and f["severity"] == "fail"
    ]
    assert matches, repr(data)
    assert data["summary"]["hard_failures"] >= 1