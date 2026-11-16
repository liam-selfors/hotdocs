import json
import sys
import tempfile
from pathlib import Path

import pytest

import spec_linter


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [alice]
sealed: true
source_path: legacy/foo
---

# Foo

## Purpose

Adds two integers together and reports the result.

## Scope

- In scope: adding two integers.
- Out of scope: everything else.

## Definitions

None.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- Initial draft.
"""

GLOSSARY_MD = """# Glossary

- **Widget** — a thing used only by this fixture.
"""

CONSTRAINTS_MD = """# Constraints

- Latency: under one second, measured by a local timer.
"""

KEYWORDLESS_REQ = """# R-FOO-001

- **R-FOO-001** — The foo component returns the sum of its two integer
  inputs to its caller.
"""

COMPLIANT_REQ_1 = """# R-FOO-001

- **R-FOO-001** — The foo component MUST return the sum of its two integer
  inputs to its caller.
"""

COMPLIANT_REQ_2 = """# R-FOO-002

- **R-FOO-002** — The foo component MUST reject a non-integer input.
"""


def _acceptance(ac_id: str, req_id: str) -> str:
    return (
        f"# {ac_id}\n\n"
        f"Covers: {req_id}\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given two integers\n"
        "When foo runs\n"
        "Then the result is their sum\n"
        "```\n"
    )


def _build_corpus(root: Path, req1_text: str) -> None:
    specs = root / "specs"
    comp = specs / "components" / "foo"
    _write(specs / "glossary.md", GLOSSARY_MD)
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(comp / "requirements" / "R-FOO-001.md", req1_text)
    _write(comp / "requirements" / "R-FOO-002.md", COMPLIANT_REQ_2)
    _write(comp / "acceptance" / "AC-FOO-001.md", _acceptance("AC-FOO-001", "R-FOO-001"))
    _write(comp / "acceptance" / "AC-FOO-002.md", _acceptance("AC-FOO-002", "R-FOO-002"))


def _findings(report):
    findings = _get(report, "findings")
    assert findings is not None, "LintReport has no findings field"
    return list(findings)


def _lint007(findings):
    return [f for f in findings if _get(f, "rule_id") == "R-LINT-007"]


def _norm(p):
    return str(p or "").replace("\\", "/")


def test_requirement_without_rfc2119_keyword_yields_fail_finding():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _build_corpus(root, KEYWORDLESS_REQ)

        report = spec_linter.lint(None, root)
        findings = _findings(report)
        lint7 = _lint007(findings)
        fails = [f for f in lint7 if _get(f, "severity") == "fail"]

        assert fails, (
            "expected a fail-severity R-LINT-007 finding; got: "
            + repr([(_get(f, "rule_id"), _get(f, "severity"), _get(f, "file")) for f in findings])
        )
        assert any(_norm(_get(f, "file")).endswith("R-FOO-001.md") for f in fails), (
            "expected the R-LINT-007 failure to point at R-FOO-001.md; got files "
            + repr([_get(f, "file") for f in fails])
        )
        # The compliant sibling requirement is not flagged.
        assert not any(_norm(_get(f, "file")).endswith("R-FOO-002.md") for f in fails)

        hard = _get(report, "hard_failures")
        if hard is None and not isinstance(report, dict):
            summary = None
        else:
            summary = None
        if hard is None:
            summary = _get(report, "summary")
            if summary is not None:
                hard = _get(summary, "hard_failures")
        if hard is not None:
            assert hard >= 1


def test_requirements_with_rfc2119_keywords_yield_no_lint007_fail():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _build_corpus(root, COMPLIANT_REQ_1)

        report = spec_linter.lint(None, root)
        findings = _findings(report)
        fails = [f for f in _lint007(findings) if _get(f, "severity") == "fail"]
        assert not fails, (
            "no R-LINT-007 failure expected when every requirement uses an "
            "RFC 2119 keyword; got: "
            + repr([(_get(f, "file"), _get(f, "message")) for f in fails])
        )


def test_cli_json_report_contains_lint007_fail_and_exit_code_1(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _build_corpus(root, KEYWORDLESS_REQ)

        capsys.readouterr()
        code = spec_linter.main(["--format=json", f"--repo-root={root}"])
        out = capsys.readouterr().out

        assert code == 1
        data = json.loads(out)
        findings = data.get("findings") if isinstance(data, dict) else None
        assert findings is not None
        fails = [
            f
            for f in findings
            if f.get("rule_id") == "R-LINT-007" and f.get("severity") == "fail"
        ]
        assert fails
        assert any(_norm(f.get("file")).endswith("R-FOO-001.md") for f in fails)