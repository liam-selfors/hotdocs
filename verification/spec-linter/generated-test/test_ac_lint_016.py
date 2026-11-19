# hotdocs-criterion: sha256:e80ed4e20086f353708d8b57504214f0b57e898ece05d67abe642766ffbb0ca1
"""AC-LINT-016: a unit file carrying YAML frontmatter is a fail-severity
finding for rule R-LINT-016."""

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
    "depends_on: []\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does one small thing for testing the linter.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the one small thing.\n"
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

REQUIREMENT_BODY = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — Foo MUST do the one small thing.\n"
)

REQUIREMENT_WITH_FRONTMATTER = (
    "---\n"
    "id: R-FOO-001\n"
    "title: Do the thing\n"
    "status: draft\n"
    "---\n"
    "\n"
) + REQUIREMENT_BODY

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given foo\n"
    "When it runs\n"
    "Then it does the one small thing\n"
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
    "- **Foo** — the component under test.\n"
)


def build_corpus(repo_root: Path, requirement_text: str) -> None:
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (specs / "product").mkdir(parents=True)
    (specs / "architecture").mkdir(parents=True)
    (specs / "vars").mkdir(parents=True)
    (specs / "decisions").mkdir(parents=True)
    (specs / "glossary.md").write_text(GLOSSARY_MD)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(requirement_text)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)
    (comp / "constraints.md").write_text(CONSTRAINTS_MD)


def lint016_fail_findings(report):
    return [
        f
        for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-016" and field(f, "severity") == "fail"
    ]


def test_requirement_file_with_frontmatter_fails_r_lint_016(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root, REQUIREMENT_WITH_FRONTMATTER)

    report = spec_linter.lint(None, repo_root)

    hits = lint016_fail_findings(report)
    assert hits, "expected a fail-severity R-LINT-016 finding, got: " + repr(
        [(field(f, "rule_id"), field(f, "severity"), field(f, "file")) for f in field(report, "findings")]
    )
    assert any(
        str(field(f, "file")).replace("\\", "/").endswith("requirements/R-FOO-001.md")
        for f in hits
    ), "R-LINT-016 finding should name the requirement file: " + repr(
        [field(f, "file") for f in hits]
    )
    assert field(report, "hard_failures") >= 1


def test_requirement_file_without_frontmatter_has_no_r_lint_016(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root, REQUIREMENT_BODY)

    report = spec_linter.lint(None, repo_root)

    assert not lint016_fail_findings(report)