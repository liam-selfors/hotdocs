# hotdocs-criterion: sha256:ed4a493b6a976ede880e1c86171d321486360c3af05f69afe2d07f773fe6fb07
import json
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
    "sealed: true\n"
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
    "When the small thing is done\n"
    "Then the small thing happened\n"
    "```\n"
)

CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "- None measurable beyond correctness; measured by tests.\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Foo** — a test component.\n"
)


def build_fixture(repo_root: Path) -> Path:
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    component_md = comp / "component.md"
    component_md.write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)
    (comp / "constraints.md").write_text(CONSTRAINTS_MD)
    (repo_root / "specs" / "glossary.md").write_text(GLOSSARY_MD)
    for d in ("product", "architecture", "vars", "decisions"):
        (repo_root / "specs" / d).mkdir(parents=True, exist_ok=True)
    return component_md


def test_sealed_without_source_path_fails_r_lint_005(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    matching = [
        f
        for f in findings
        if field(f, "rule_id") == "R-LINT-005" and field(f, "severity") == "fail"
    ]
    assert matching, (
        "expected a fail-severity R-LINT-005 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "message")) for f in findings])
    )
    assert any(
        str(field(f, "file")).replace("\\", "/").endswith("specs/components/foo/component.md")
        for f in matching
    )
    assert field(report, "hard_failures") >= 1


def test_cli_reports_r_lint_005_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    assert any(
        f["rule_id"] == "R-LINT-005" and f["severity"] == "fail"
        for f in data["findings"]
    )
    assert data["summary"]["hard_failures"] >= 1