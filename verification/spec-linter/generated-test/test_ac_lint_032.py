"""AC-LINT-032 (Covers: R-LINT-032).

Given a project holding .hotdocs-tool.json with components "foo" and
"cache-manager", when the linter runs on it, then "cache-manager" gets an
R-LINT-032 fail finding and "foo" none.

Given the same project without .hotdocs-tool.json, or the tool's own
repository, when the linter runs on it, then there is no R-LINT-032 finding.
"""

import json
import re
from pathlib import Path

import pytest

import spec_linter


RULE = "R-LINT-032"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _tool_root() -> Path:
    """Parent of the nearest directory named `gen` above spec_linter's file."""
    here = Path(spec_linter.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    pytest.skip("spec_linter is not installed under a `gen` directory; no tool root")


def _shadowed_slug(tool_root: Path) -> str:
    gen = tool_root / "gen"
    if (gen / "cache-manager").is_dir():
        return "cache-manager"
    pytest.skip("tool root's gen/ has no cache-manager directory to shadow")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_component(specs: Path, slug: str, prefix: str) -> None:
    cdir = specs / "components" / slug
    title = slug.replace("-", " ").title()
    _write(
        cdir / "component.md",
        f"""---
id: comp-{slug}
title: {title}
status: draft
owners: [test-team]
sealed: true
source_path: legacy/{slug}/
---

# {title}

## Purpose

Stores and returns values for the {slug} test fixture component.

## Scope

- In scope: returning a stored value for a known key.
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
""",
    )
    _write(
        cdir / "requirements" / f"R-{prefix}-001.md",
        f"""# R-{prefix}-001

**R-{prefix}-001** — The component MUST return the stored value for a
known key.
""",
    )
    _write(
        cdir / "acceptance" / f"AC-{prefix}-001.md",
        f"""# AC-{prefix}-001

Covers: R-{prefix}-001
Kind: compiled

```gherkin
Given a stored value "v" under key "k"
When the value for key "k" is requested
Then the result is "v"
```
""",
    )
    _write(
        cdir / "constraints.md",
        "# Constraints\n\n- None beyond the defaults.\n",
    )


def _make_project(root: Path, shadowed: str, with_marker: bool) -> Path:
    specs = root / "specs"
    _make_component(specs, "foo", "FOO")
    _make_component(specs, shadowed, "SHADOW")
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing used only by test fixtures.\n",
    )
    if with_marker:
        _write(root / ".hotdocs-tool.json", json.dumps({}) + "\n")
    return root


def _rule_findings(report):
    return [f for f in field(report, "findings") if field(f, "rule_id") == RULE]


def _names_slug(finding, slug: str) -> bool:
    text = f"{field(finding, 'message')} {field(finding, 'file')}"
    return re.search(r"(?<![\w-])" + re.escape(slug) + r"(?![\w-])", text) is not None


def test_marker_project_flags_shadowing_component_only(tmp_path):
    tool_root = _tool_root()
    shadowed = _shadowed_slug(tool_root)
    if (tool_root / "gen" / "foo").exists():
        pytest.skip("tool root's gen/ unexpectedly holds a foo directory")

    repo = _make_project(tmp_path / "project", shadowed, with_marker=True)
    report = spec_linter.lint(None, repo)
    findings = _rule_findings(report)

    shadow_hits = [
        f for f in findings
        if field(f, "severity") == "fail" and _names_slug(f, shadowed)
    ]
    assert shadow_hits, (
        f"expected an {RULE} fail finding naming {shadowed!r}; got "
        f"{[(field(f, 'severity'), field(f, 'file'), field(f, 'message')) for f in findings]}"
    )

    foo_hits = [f for f in findings if _names_slug(f, "foo")]
    assert not foo_hits, (
        f"'foo' is not under the tool's gen/ and must get no {RULE} finding; got "
        f"{[(field(f, 'file'), field(f, 'message')) for f in foo_hits]}"
    )

    # Every R-LINT-032 finding is about the shadowing component.
    for f in findings:
        assert _names_slug(f, shadowed), field(f, "message")

    # A fail finding counts toward hard failures.
    assert field(report, "hard_failures") >= 1


def test_marker_project_cli_reports_rule_and_exits_1(tmp_path, capsys):
    tool_root = _tool_root()
    shadowed = _shadowed_slug(tool_root)
    if (tool_root / "gen" / "foo").exists():
        pytest.skip("tool root's gen/ unexpectedly holds a foo directory")

    repo = _make_project(tmp_path / "project", shadowed, with_marker=True)
    capsys.readouterr()
    code = spec_linter.main([f"--repo-root={repo}", "--format=json"])
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    hits = [
        f for f in doc["findings"]
        if f["rule_id"] == RULE and f["severity"] == "fail" and _names_slug(f, shadowed)
    ]
    assert hits


def test_project_without_marker_has_no_rule_finding(tmp_path):
    tool_root = _tool_root()
    shadowed = _shadowed_slug(tool_root)

    repo = _make_project(tmp_path / "project", shadowed, with_marker=False)
    assert not (repo / ".hotdocs-tool.json").exists()
    report = spec_linter.lint(None, repo)
    findings = _rule_findings(report)
    assert findings == [], [
        (field(f, "file"), field(f, "message")) for f in findings
    ]


def test_tool_own_repository_has_no_rule_finding():
    tool_root = _tool_root()
    if not (tool_root / "specs").is_dir():
        pytest.skip("tool root carries no specs/ tree to lint")
    report = spec_linter.lint(None, tool_root)
    findings = _rule_findings(report)
    assert findings == [], [
        (field(f, "file"), field(f, "message")) for f in findings
    ]