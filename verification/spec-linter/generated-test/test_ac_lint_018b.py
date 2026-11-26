# hotdocs-criterion: sha256:0261554436d9e34e2e6933504abc0e4b16be951d1609d966ff37cf82854edeaf
"""AC-LINT-018b: a depends_on_guarantees entry that resolves to no G-id
yields a fail-severity R-LINT-018 finding."""

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
    "depends_on_guarantees: [G-DOES-NOT-EXIST]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does a small thing for testing.\n"
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
    "**R-FOO-001** — Foo MUST do the small thing.\n"
)

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given a foo\n"
    "When it runs\n"
    "Then it does the small thing\n"
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
    "- **Foo** — a test component.\n"
)


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (comp / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD, encoding="utf-8")
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD, encoding="utf-8")
    (comp / "constraints.md").write_text(CONSTRAINTS_MD, encoding="utf-8")
    (specs / "glossary.md").write_text(GLOSSARY_MD, encoding="utf-8")
    for sub in ("product", "architecture", "vars", "decisions"):
        (specs / sub).mkdir(parents=True, exist_ok=True)


def test_ac_lint_018b_unresolved_guarantee_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    matching = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-018" and field(f, "severity") == "fail"
    ]
    assert matching, (
        "expected a fail-severity R-LINT-018 finding; got: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "message")) for f in findings])
    )
    assert field(report, "hard_failures") >= 1