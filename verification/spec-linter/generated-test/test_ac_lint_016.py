# hotdocs-criterion: sha256:e80ed4e20086f353708d8b57504214f0b57e898ece05d67abe642766ffbb0ca1
import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [test-team]
sealed: true
source_path: legacy/foo/
---

# Foo

## Purpose

Foo does one small thing for the test corpus.

## Scope

- In scope: the one small thing.
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

REQUIREMENT_BODY = """# R-FOO-001

**R-FOO-001** — Foo MUST do the one small thing.
"""

REQUIREMENT_WITH_FRONTMATTER = """---
id: R-FOO-001
title: Foo requirement
status: draft
---

""" + REQUIREMENT_BODY

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: compiled

```gherkin
Given foo
When foo runs
Then the one small thing happens
```
"""

CONSTRAINTS_MD = """# Constraints

- Foo runs in under one second, measured by timing a single call.
"""

GLOSSARY_MD = """# Glossary

- **Foo** — the test component.
"""


def _build_corpus(root: Path, with_frontmatter: bool) -> Path:
    comp = root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    req_text = REQUIREMENT_WITH_FRONTMATTER if with_frontmatter else REQUIREMENT_BODY
    req_path = comp / "requirements" / "R-FOO-001.md"
    req_path.write_text(req_text)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)
    (comp / "constraints.md").write_text(CONSTRAINTS_MD)
    (root / "specs" / "glossary.md").write_text(GLOSSARY_MD)
    return req_path


def _lint016_findings(findings):
    return [f for f in findings if field(f, "rule_id") == "R-LINT-016"]


def _norm(path_str):
    return str(path_str).replace("\\", "/")


def test_requirement_file_with_frontmatter_fails_r_lint_016(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, with_frontmatter=True)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    hits = [
        f
        for f in _lint016_findings(findings)
        if field(f, "severity") == "fail"
        and _norm(field(f, "file")).endswith("requirements/R-FOO-001.md")
    ]
    assert hits, (
        "expected a fail-severity R-LINT-016 finding on R-FOO-001.md, got: "
        + repr([(field(f, "rule_id"), field(f, "severity"), field(f, "file")) for f in findings])
    )

    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 1


def test_requirement_file_without_frontmatter_has_no_r_lint_016(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, with_frontmatter=False)

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))

    assert _lint016_findings(findings) == [], repr(
        [(field(f, "file"), field(f, "message")) for f in _lint016_findings(findings)]
    )


def test_cli_reports_r_lint_016_fail_and_exits_1(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, with_frontmatter=True)

    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out

    doc = json.loads(out)
    hits = [
        f
        for f in doc["findings"]
        if f["rule_id"] == "R-LINT-016"
        and f["severity"] == "fail"
        and _norm(f["file"]).endswith("requirements/R-FOO-001.md")
    ]
    assert hits, doc["findings"]
    assert doc["summary"]["hard_failures"] >= 1
    assert code == 1