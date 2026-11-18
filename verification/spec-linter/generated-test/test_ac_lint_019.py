# hotdocs-criterion: sha256:b9181b28b410cbb32a8a003c1809abb5cf1f4eb69b0490e912b109f973897271
"""AC-LINT-019: a spec line ending in two trailing spaces yields a fail-severity
R-LINT-019 finding naming that line."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write raw bytes so trailing whitespace and newlines are preserved exactly.
    path.write_bytes(text.encode("utf-8"))


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does one small thing for testing.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the one thing.\n"
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

CLEAN_REQUIREMENT = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — Foo MUST do the one thing.\n"
    "Matches existing behavior; do not regenerate.\n"
)

# Line 3 ends in exactly two trailing spaces.
DIRTY_REQUIREMENT = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — Foo MUST do the one thing.  \n"
    "Matches existing behavior; do not regenerate.\n"
)
DIRTY_LINE = 3

ACCEPTANCE = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given foo\n"
    "When it runs\n"
    "Then it does the one thing\n"
    "```\n"
)

CONSTRAINTS = (
    "# Constraints\n"
    "\n"
    "- None beyond existing behavior.\n"
)

GLOSSARY = (
    "# Glossary\n"
    "\n"
    "- **Foo** — a test component.\n"
)

REQ_REL = "specs/components/foo/requirements/R-FOO-001.md"


def _build_corpus(repo_root, requirement_text):
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", requirement_text)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)


def _norm(file_value):
    return str(file_value).replace("\\", "/")


def _file_matches(file_value):
    f = _norm(file_value)
    return f == REQ_REL or f.endswith("/" + REQ_REL)


def _lint019(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == "R-LINT-019"]


def test_clean_corpus_has_no_trailing_whitespace_finding(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, CLEAN_REQUIREMENT)
    report = spec_linter.lint(None, repo_root)
    assert _lint019(report) == []


def test_trailing_two_spaces_reports_fail_finding_naming_line(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, DIRTY_REQUIREMENT)

    report = spec_linter.lint(None, repo_root)
    findings = _lint019(report)

    assert findings, "expected an R-LINT-019 finding for the trailing-whitespace line"

    matching = [
        f
        for f in findings
        if _file_matches(field(f, "file")) and field(f, "line") == DIRTY_LINE
    ]
    assert matching, (
        "no R-LINT-019 finding names "
        + repr(REQ_REL)
        + " line "
        + repr(DIRTY_LINE)
        + "; got "
        + repr([(field(f, "file"), field(f, "line")) for f in findings])
    )
    for f in matching:
        assert field(f, "severity") == "fail"

    # Only the one offending line is reported under this rule.
    for f in findings:
        assert _file_matches(field(f, "file"))
        assert field(f, "line") == DIRTY_LINE

    assert field(report, "hard_failures") >= 1


def test_trailing_whitespace_fails_cli_exit_code(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, DIRTY_REQUIREMENT)
    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    assert code == 1