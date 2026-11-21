# hotdocs-criterion: sha256:2e239e04d9e452db4a7286d11aba7937fc43d304a0b88433c2d982733f655d51
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRODUCT = (
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


def component_md(status_lines, open_questions):
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        + status_lines
        + "owners: [team-a]\n"
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
        + open_questions
        + "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n"
    )


REQ = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `make_foo()` MUST return the string `\"foo\"`.\n"
)

LIB = (
    "# Library\n"
    "\n"
    "One module file, `foo.py`.\n"
    "\n"
    "```\n"
    "make_foo() -> str\n"
    "```\n"
)

AC = (
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


def write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build(root, status_lines, open_questions):
    write(root, "specs/product/foo.md", PRODUCT)
    write(root, "specs/components/foo/component.md",
          component_md(status_lines, open_questions))
    write(root, "specs/components/foo/requirements/R-FOO-001.md", REQ)
    write(root, "specs/components/foo/interface/library.md", LIB)
    write(root, "specs/components/foo/acceptance/AC-FOO-001.md", AC)
    write(root, "specs/components/foo/constraints.md", CONSTRAINTS)


RATIFIED = "status: ratified\nlast_ratified_commit: 0000000\n"
DRAFT = "status: draft\n"
NON_EMPTY_OQ = "- Should a foo ever be a bar?\n"


def r_lint_002_fails(report):
    return [
        f for f in field(report, "findings")
        if field(f, "rule_id") == "R-LINT-002" and field(f, "severity") == "fail"
    ]


def test_ratified_with_open_questions_fails_r_lint_002(tmp_path):
    repo_root = tmp_path / "repo"
    build(repo_root, RATIFIED, NON_EMPTY_OQ)

    report = spec_linter.lint(None, repo_root)

    hits = r_lint_002_fails(report)
    assert len(hits) >= 1
    files = [str(field(f, "file")).replace("\\", "/") for f in hits]
    assert "specs/components/foo/component.md" in files
    assert field(report, "hard_failures") >= 1


def test_draft_with_open_questions_has_no_r_lint_002(tmp_path):
    repo_root = tmp_path / "repo"
    build(repo_root, DRAFT, NON_EMPTY_OQ)

    report = spec_linter.lint(None, repo_root)

    assert r_lint_002_fails(report) == []


def test_cli_reports_r_lint_002_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    build(repo_root, RATIFIED, NON_EMPTY_OQ)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    assert any(
        f["rule_id"] == "R-LINT-002" and f["severity"] == "fail"
        for f in doc["findings"]
    )