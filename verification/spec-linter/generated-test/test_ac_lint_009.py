# hotdocs-criterion: sha256:542b318d0f9b892dd14272b5ec4be8672a59c795715ca73e79b73c89f5ecf35c
"""AC-LINT-009: a Covers: tag naming a nonexistent R-id is a fail finding for R-LINT-009."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [test-team]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo returns a fixed greeting for testing the linter.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: returning a greeting.\n"
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
    "**R-FOO-001** \u2014 Foo MUST return the greeting `hello`.\n"
)

AC_GOOD_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given foo\n"
    "When foo is called\n"
    "Then it returns hello\n"
    "```\n"
)

AC_DANGLING_MD = (
    "# AC-FOO-002\n"
    "\n"
    "Covers: R-DOES-NOT-EXIST\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given foo\n"
    "When foo is called\n"
    "Then it returns hello\n"
    "```\n"
)

CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "- Foo returns within 1 second, measured by a timer around the call.\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Greeting** \u2014 the text foo returns.\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    for sub in ("product", "architecture", "vars", "decisions"):
        (specs / sub).mkdir(parents=True, exist_ok=True)
    _write(specs / "glossary.md", GLOSSARY_MD)
    comp = specs / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_GOOD_MD)
    _write(comp / "acceptance" / "AC-FOO-002.md", AC_DANGLING_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    (repo_root / "gen").mkdir(parents=True, exist_ok=True)
    (repo_root / "verification").mkdir(parents=True, exist_ok=True)


def test_dangling_covers_tag_is_fail_finding_for_r_lint_009(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    lint_009 = [
        f for f in findings
        if field(f, "rule_id") == "R-LINT-009"
        and field(f, "severity") == "fail"
    ]
    assert lint_009, (
        "expected a fail-severity R-LINT-009 finding; got: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "file"),
                 field(f, "message")) for f in findings])
    )

    # The finding concerns the criterion carrying the dangling Covers: tag.
    assert any("AC-FOO-002" in str(field(f, "file")) for f in lint_009), (
        "expected an R-LINT-009 fail finding on AC-FOO-002.md; got: "
        + repr([(field(f, "file"), field(f, "message")) for f in lint_009])
    )

    # A fail finding counts as a hard failure.
    assert field(report, "hard_failures") >= 1