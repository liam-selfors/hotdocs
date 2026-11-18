# hotdocs-criterion: sha256:62658c384b0d81e29bde1789ebe40feca12058f202b351fc9d316ae8691ba8c1
"""AC-SIZE-001: a component whose generated-code LOC exceeds 1500 gets a
fail-severity R-SIZE-001 finding naming `generated_code_loc`."""

from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [alice]\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does a small thing for testing purposes.\n"
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
    "- Initial version.\n"
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
    "Given foo\n"
    "When it runs\n"
    "Then it does the small thing\n"
    "```\n"
)

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

GLOSSARY_MD = "# Glossary\n\n- **Foo** — a test term.\n"


def build_fixture(repo_root: Path, loc: int) -> None:
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)
    (comp / "constraints.md").write_text(CONSTRAINTS_MD)
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_MD)

    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True)
    lines = []
    for i in range(loc):
        lines.append("x_" + str(i) + " = " + repr(i))
    (gen_dir / "foo.py").write_text("\n".join(lines) + "\n")


def test_generated_code_loc_over_1500_is_fail_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, 2000)

    findings = size_checker.check(repo_root)
    assert isinstance(findings, list)

    matching = [
        f
        for f in findings
        if field(f, "rule_id") == "R-SIZE-001"
        and field(f, "severity") == "fail"
        and "generated_code_loc" in field(f, "message")
    ]
    assert matching, (
        "expected a fail-severity R-SIZE-001 finding naming generated_code_loc, got: "
        + repr(findings)
    )