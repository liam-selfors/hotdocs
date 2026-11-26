# hotdocs-criterion: sha256:ead26c99ccc9f5d941cd75f50d695f9ed75487160716f8e4b5f73a7e2b7407f1
"""AC-LINT-009: a Covers: tag naming a nonexistent R-id is a fail-severity
R-LINT-009 finding (backward traceability)."""

import io
import json
import contextlib
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    "Foo does a small thing for the test fixture.\n"
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
    "**R-FOO-001** \u2014 Foo MUST do the small thing.\n"
)


def criterion(ac_id, covers):
    return (
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + covers + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a foo\n"
        "When the small thing is requested\n"
        "Then the small thing happens\n"
        "```\n"
    )


CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "- None measurable beyond the fixture.\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Foo** \u2014 the fixture component.\n"
)


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    write(comp / "acceptance" / "AC-FOO-001.md", criterion("AC-FOO-001", "R-FOO-001"))
    write(
        comp / "acceptance" / "AC-FOO-002.md",
        criterion("AC-FOO-002", "R-DOES-NOT-EXIST"),
    )
    write(comp / "constraints.md", CONSTRAINTS_MD)
    write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    return repo_root


def r009_findings(findings):
    return [f for f in findings if field(f, "rule_id") == "R-LINT-009"]


def test_dangling_covers_is_fail_finding_for_r_lint_009(tmp_path):
    repo_root = build_fixture(tmp_path)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    r009 = r009_findings(findings)
    failing = [f for f in r009 if field(f, "severity") == "fail"]
    assert failing, (
        "expected a fail-severity R-LINT-009 finding, got: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "file"))
                for f in findings])
    )

    # The finding concerns the dangling criterion, not the valid one.
    assert any(
        "AC-FOO-002" in str(field(f, "file"))
        or "R-DOES-NOT-EXIST" in str(field(f, "message"))
        for f in failing
    )
    assert not any("AC-FOO-001" in str(field(f, "file")) for f in r009)

    assert field(report, "hard_failures") >= 1


def test_dangling_covers_fails_cli_json(tmp_path):
    repo_root = build_fixture(tmp_path)

    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])

    assert code == 1, err.getvalue()
    doc = json.loads(out.getvalue())
    assert any(
        f["rule_id"] == "R-LINT-009" and f["severity"] == "fail"
        for f in doc["findings"]
    )
    assert doc["summary"]["hard_failures"] >= 1