# hotdocs-criterion: sha256:b9181b28b410cbb32a8a003c1809abb5cf1f4eb69b0490e912b109f973897271
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does one small thing for its callers.\n"
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

# Line 3 (1-based) ends in exactly two trailing spaces; no other line does.
REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — Foo MUST do the one small thing.  \n"
    "It MUST NOT do anything else.\n"
)
TRAILING_LINE = 3

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
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
    "- None beyond the defaults.\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Foo** — the fixture component.\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _build_corpus(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    return comp / "requirements" / "R-FOO-001.md"


def _norm(p):
    return str(p).replace("\\", "/")


def test_ac_lint_019_trailing_whitespace_is_fail_finding_naming_line(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    req_path = _build_corpus(repo_root)

    # Sanity: the fixture really has exactly one line with trailing whitespace.
    raw_lines = req_path.read_bytes().decode("utf-8").split("\n")
    offending = [
        i + 1 for i, line in enumerate(raw_lines) if line != line.rstrip()
    ]
    assert offending == [TRAILING_LINE]
    assert raw_lines[TRAILING_LINE - 1].endswith("thing.  ")

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    rel = "specs/components/foo/requirements/R-FOO-001.md"
    lint019 = [f for f in findings if field(f, "rule_id") == "R-LINT-019"]
    assert lint019, "expected an R-LINT-019 finding, got: " + repr(findings)

    def names_file(f):
        file_value = _norm(field(f, "file"))
        return file_value == rel or file_value.endswith("/" + rel)

    matching = [
        f
        for f in lint019
        if names_file(f) and field(f, "line") == TRAILING_LINE
    ]
    assert matching, (
        "no R-LINT-019 finding naming "
        + rel
        + " line "
        + repr(TRAILING_LINE)
        + "; got: "
        + repr(lint019)
    )
    for f in matching:
        assert field(f, "severity") == "fail"

    # The only line with trailing whitespace is that one line.
    for f in lint019:
        assert names_file(f), "unexpected R-LINT-019 finding: " + repr(f)
        assert field(f, "line") == TRAILING_LINE, (
            "unexpected R-LINT-019 finding: " + repr(f)
        )

    assert field(report, "hard_failures") >= 1