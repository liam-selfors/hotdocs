# hotdocs-criterion: sha256:d516809a8bcf9286c75d36dde92f2bacdd1457f33090ecbeea291f6aabff357c
import pytest
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_BODY = (
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Does foo things.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: foo.\n"
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


def build_fixture(repo_root, sealed_line):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    for d in ("product", "architecture", "vars", "decisions"):
        (specs / d).mkdir(parents=True, exist_ok=True)

    frontmatter = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        + sealed_line
        + "---\n"
    )
    (comp / "component.md").write_text(frontmatter + "\n" + COMPONENT_BODY)

    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — The component MUST do foo.\n"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a foo\n"
        "When foo runs\n"
        "Then foo happens\n"
        "```\n"
    )
    (comp / "constraints.md").write_text(
        "# Constraints\n"
        "\n"
        "None.\n"
    )
    (specs / "glossary.md").write_text(
        "# Glossary\n"
        "\n"
        "- **Foo** — a foo thing.\n"
    )


@pytest.mark.parametrize(
    "sealed_line",
    ["sealed: false\n", ""],
    ids=["sealed-false", "sealed-absent"],
)
def test_non_sealed_component_without_realizes_fails_r_lint_006(tmp_path, sealed_line):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, sealed_line)

    report = spec_linter.lint(None, repo_root)

    findings = list(field(report, "findings"))
    matching = [f for f in findings if field(f, "rule_id") == "R-LINT-006"]
    assert matching, (
        "expected an R-LINT-006 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "severity")) for f in findings])
    )
    assert any(field(f, "severity") == "fail" for f in matching), (
        "expected R-LINT-006 with fail severity, got: "
        + repr([field(f, "severity") for f in matching])
    )
    assert field(report, "hard_failures") >= 1