# hotdocs-criterion: sha256:54b746f0c076c47f64b25bddd194871c74aa3636d391da822e09591841594f7f
"""AC-LINT-019: a spec line ending in two trailing spaces is a fail-severity
R-LINT-019 finding naming that line."""

from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_LINES = [
    "---",
    "id: comp-foo",
    "title: Foo",
    "status: draft",
    "owners: [pipeline-team]",
    "depends_on: []",
    "sealed: true",
    "source_path: legacy/foo/",
    "---",
    "",
    "# Foo",
    "",
    "## Purpose",
    "",
    "Foo does one small thing for the tests.",
    "",
    "## Scope",
    "",
    "- In scope: the one thing.",
    "- Out of scope: everything else.",
    "",
    "## Definitions",
    "",
    "None.",
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
    "See `interface/data/`.",
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
    "## Change log",
    "",
    "- Initial draft.",
]

REQUIREMENT_LINES = [
    "# R-FOO-001",
    "",
    "**R-FOO-001** — Foo MUST do the one thing.",
    "",
]

ACCEPTANCE_LINES = [
    "# AC-FOO-001",
    "",
    "Covers: R-FOO-001",
    "Kind: generated-test",
    "",
    "```gherkin",
    "Given a foo",
    "When it runs",
    "Then it does the one thing",
    "```",
]

CONSTRAINTS_LINES = [
    "# Constraints",
    "",
    "- None beyond the defaults; measured by review.",
]

GLOSSARY_LINES = [
    "# Glossary",
    "",
    "- **Foo** — a test component.",
]

COMP_REL = "specs/components/foo/component.md"
REQ_REL = "specs/components/foo/requirements/R-FOO-001.md"


def write_lines(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_corpus(repo_root, trailing=None):
    """trailing: (rel_path, 1-based line number) whose line gets two trailing spaces."""
    files = {
        COMP_REL: list(COMPONENT_LINES),
        REQ_REL: list(REQUIREMENT_LINES),
        "specs/components/foo/acceptance/AC-FOO-001.md": list(ACCEPTANCE_LINES),
        "specs/components/foo/constraints.md": list(CONSTRAINTS_LINES),
        "specs/glossary.md": list(GLOSSARY_LINES),
    }
    if trailing is not None:
        rel, lineno = trailing
        files[rel][lineno - 1] = files[rel][lineno - 1] + "  "
    for rel, lines in files.items():
        write_lines(repo_root / rel, lines)


def names_file(finding_file, repo_root, rel):
    text = str(finding_file).replace("\\", "/")
    if text == rel:
        return True
    try:
        return Path(text).resolve().relative_to(repo_root.resolve()).as_posix() == rel
    except (ValueError, OSError):
        return False


def lint_019_findings(repo_root):
    report = spec_linter.lint(None, repo_root)
    findings = field(report, "findings")
    return report, [f for f in findings if field(f, "rule_id") == "R-LINT-019"]


def test_clean_corpus_has_no_trailing_whitespace_finding(tmp_path):
    repo_root = tmp_path / "repo"
    build_corpus(repo_root)
    _, found = lint_019_findings(repo_root)
    assert found == []


@pytest.mark.parametrize(
    "rel, lineno",
    [
        (REQ_REL, 3),   # body line of a unit file
        (COMP_REL, 3),  # a frontmatter line ("title: Foo")
        (COMP_REL, 15), # a body line of component.md
    ],
)
def test_two_trailing_spaces_is_fail_finding_naming_line(tmp_path, rel, lineno):
    repo_root = tmp_path / "repo"
    build_corpus(repo_root, trailing=(rel, lineno))

    # The fixture really has exactly that one line with trailing whitespace.
    text = (repo_root / rel).read_text(encoding="utf-8")
    assert text.splitlines()[lineno - 1].endswith("  ")

    report, found = lint_019_findings(repo_root)

    assert len(found) == 1, found
    finding = found[0]
    assert field(finding, "severity") == "fail"
    assert names_file(field(finding, "file"), repo_root, rel), field(finding, "file")
    assert field(finding, "line") == lineno
    assert isinstance(field(finding, "message"), str)
    assert field(report, "hard_failures") >= 1