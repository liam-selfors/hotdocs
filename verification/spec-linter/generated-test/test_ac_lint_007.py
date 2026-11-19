# hotdocs-criterion: sha256:5fc4d0246fbc8b3a64252ef19c136c88bf1b8793832219122ae90606823bf0e4
"""AC-LINT-007: a requirement with no RFC 2119 keyword yields a fail-severity
finding for rule R-LINT-007."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo echoes its input back to the caller.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: echoing input.\n"
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

# Deliberately free of every RFC 2119 keyword, in any case.
REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "- **R-FOO-001** — The component returns its input unchanged to the caller.\n"
)

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given an input of \"abc\"\n"
    "When foo runs\n"
    "Then the output is \"abc\"\n"
    "```\n"
)

CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "- Echo completes in under 1 second, measured by a timer around the call.\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Echo** — returning the input unchanged.\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)


def test_requirement_without_rfc2119_keyword_fails_r_lint_007(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    matching = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-007" and field(f, "severity") == "fail"
    ]
    assert matching, (
        "expected a fail-severity R-LINT-007 finding, got: "
        + repr(
            [
                (field(f, "rule_id"), field(f, "severity"), field(f, "file"), field(f, "message"))
                for f in findings
            ]
        )
    )
    assert field(report, "hard_failures") >= 1