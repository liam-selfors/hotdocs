# hotdocs-criterion: sha256:b6d1c145de1c5dc7cfda298db73d2a2827470a61ac54bc56c1c3389e1cbaac9a
import spec_linter
from pathlib import Path


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

REQ_1 = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — Foo MUST return the input unchanged.\n"
)

REQ_2 = (
    "# R-FOO-002\n"
    "\n"
    "**R-FOO-002** — Foo MUST reject an empty input.\n"
)

# Missing the Kind: tag entirely.
AC_1_NO_KIND = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "\n"
    "```gherkin\n"
    "Given an input \"abc\"\n"
    "When foo runs\n"
    "Then the result is \"abc\"\n"
    "```\n"
)

# Well-formed control criterion with a Kind: tag.
AC_2_WITH_KIND = (
    "# AC-FOO-002\n"
    "\n"
    "Covers: R-FOO-002\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given an empty input\n"
    "When foo runs\n"
    "Then foo raises ValueError\n"
    "```\n"
)

CONSTRAINTS = "# Constraints\n\nNone.\n"

GLOSSARY = (
    "# Glossary\n"
    "\n"
    "- **Foo thing** — a thing used only by tests.\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    _write(specs / "glossary.md", GLOSSARY)
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQ_1)
    _write(comp / "requirements" / "R-FOO-002.md", REQ_2)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_1_NO_KIND)
    _write(comp / "acceptance" / "AC-FOO-002.md", AC_2_WITH_KIND)
    _write(comp / "constraints.md", CONSTRAINTS)


def test_ac_missing_kind_yields_fail_finding_for_r_lint_010(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    lint010 = [f for f in findings if str(field(f, "rule_id")) == "R-LINT-010"]
    assert lint010, (
        "expected an R-LINT-010 finding; got: "
        + repr([(field(f, "rule_id"), field(f, "file")) for f in findings])
    )

    fail_on_missing = [
        f for f in lint010
        if str(field(f, "severity")) == "fail"
        and "AC-FOO-001" in str(field(f, "file"))
    ]
    assert fail_on_missing, (
        "expected a fail-severity R-LINT-010 finding on AC-FOO-001; got: "
        + repr([(field(f, "severity"), field(f, "file"), field(f, "message")) for f in lint010])
    )

    # The well-formed criterion (with Kind:) must not be flagged by R-LINT-010.
    on_control = [f for f in lint010 if "AC-FOO-002" in str(field(f, "file"))]
    assert on_control == [], (
        "R-LINT-010 wrongly flagged a criterion that has a Kind: tag: "
        + repr([(field(f, "file"), field(f, "message")) for f in on_control])
    )

    assert field(report, "hard_failures") >= 1