# hotdocs-criterion: sha256:9eb73aaca947daba2323f06174ec579b181b848512cdfdf9547072a022128bbd
import io
import json
import contextlib
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    "Foo does one small thing for testing.\n"
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

REQ_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — Foo MUST return the input unchanged.\n"
)

AC_GOOD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given an input\n"
    "When foo runs\n"
    "Then the output equals the input\n"
    "```\n"
)

AC_DANGLING = (
    "# AC-FOO-002\n"
    "\n"
    "Covers: R-DOES-NOT-EXIST\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given an input\n"
    "When foo runs\n"
    "Then something happens\n"
    "```\n"
)

CONSTRAINTS_MD = (
    "# Constraints\n"
    "\n"
    "- Foo MUST complete in under 1 second, measured by wall clock.\n"
)

GLOSSARY_MD = (
    "# Glossary\n"
    "\n"
    "- **Foo** — a test component.\n"
)


def _build(repo_root, dangling):
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQ_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_GOOD)
    if dangling:
        _write(comp / "acceptance" / "AC-FOO-002.md", AC_DANGLING)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    return comp


def _r009_fails(findings):
    return [
        f for f in findings
        if field(f, "rule_id") == "R-LINT-009" and field(f, "severity") == "fail"
    ]


def test_dangling_covers_yields_fail_finding_for_r_lint_009(tmp_path):
    repo_root = tmp_path / "repo"
    _build(repo_root, dangling=True)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    hits = _r009_fails(findings)

    assert hits, "expected a fail-severity R-LINT-009 finding, got: " + repr(findings)
    assert any(
        str(field(f, "file")).endswith("AC-FOO-002.md")
        or "R-DOES-NOT-EXIST" in str(field(f, "message"))
        for f in hits
    ), repr(hits)
    assert field(report, "hard_failures") >= 1


def test_resolving_covers_yields_no_r_lint_009_failure(tmp_path):
    repo_root = tmp_path / "repo"
    _build(repo_root, dangling=False)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    assert _r009_fails(findings) == [], repr(findings)


def test_cli_json_reports_r_lint_009_and_exits_1(tmp_path):
    repo_root = tmp_path / "repo"
    _build(repo_root, dangling=True)

    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])

    assert code == 1, "stderr: " + err.getvalue()
    doc = json.loads(out.getvalue())
    hits = [
        f for f in doc["findings"]
        if f["rule_id"] == "R-LINT-009" and f["severity"] == "fail"
    ]
    assert hits, repr(doc)
    assert doc["summary"]["hard_failures"] >= 1