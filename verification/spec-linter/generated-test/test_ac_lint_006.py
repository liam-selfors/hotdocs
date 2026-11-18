# hotdocs-criterion: sha256:d516809a8bcf9286c75d36dde92f2bacdd1457f33090ecbeea291f6aabff357c
"""AC-LINT-006 (covers R-LINT-006).

Given a component component.md with sealed: false (or absent) and zero
realizes entries, when hotdocs lint runs against it, then the report
contains a fail-severity finding for rule R-LINT-006.
"""

import io
import json
import contextlib
from pathlib import Path

import pytest

import spec_linter


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_BODY = """
# {title}

## Purpose

A small synthetic component used only as a lint fixture.

## Scope

- In scope: fixture behavior.
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


def _write_component(repo_root: Path, slug: str, upper: str, frontmatter_extra: str) -> None:
    comp_dir = repo_root / "specs" / "components" / slug
    title = f"{slug.capitalize()} Component"
    fm = (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [alice]\n"
        f"{frontmatter_extra}"
        "---\n"
    )
    _write(comp_dir / "component.md", fm + COMPONENT_BODY.format(title=title))
    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — The component MUST do its one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a fixture\nWhen it runs\nThen it does its one thing\n```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n- None beyond the defaults. Measured by inspection.\n",
    )


def _write_glossary(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic test corpus.\n",
    )


def _write_product(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "product" / "p-fixture.md",
        "---\n"
        "id: P-FIXTURE\n"
        "title: Fixture Capability\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n\n"
        "# Fixture Capability\n\n## Purpose\n\nA fixture capability.\n\n"
        "## Scope\n\n- Fixture only.\n\n"
        "### CS-FIXTURE-001\n\nCovers: P-FIXTURE\nKind: llm-judge\n\n"
        "```gherkin\nGiven a fixture\nWhen it runs\nThen it works\n```\n",
    )


def _findings(report):
    findings = _get(report, "findings", None)
    assert findings is not None, "LintReport exposes no findings"
    return list(findings)


def _lint_006_findings(report):
    return [f for f in _findings(report) if _get(f, "rule_id") == "R-LINT-006"]


def _file_str(finding) -> str:
    return str(_get(finding, "file", "") or "").replace("\\", "/")


UNSEALED_NO_REALIZES_VARIANTS = {
    "sealed_absent_realizes_absent": "",
    "sealed_false_realizes_absent": "sealed: false\n",
    "sealed_absent_realizes_empty": "realizes: []\n",
    "sealed_false_realizes_empty": "sealed: false\nrealizes: []\n",
}


@pytest.mark.parametrize(
    "extra",
    list(UNSEALED_NO_REALIZES_VARIANTS.values()),
    ids=list(UNSEALED_NO_REALIZES_VARIANTS.keys()),
)
def test_unsealed_component_without_realizes_fails_r_lint_006(tmp_path, extra):
    repo_root = tmp_path / "repo"
    _write_glossary(repo_root)
    _write_component(repo_root, "foo", "FOO", extra)

    report = spec_linter.lint(None, repo_root)

    hits = _lint_006_findings(report)
    assert hits, (
        "expected an R-LINT-006 finding for an unsealed component with zero "
        f"realizes entries; got rule ids {[_get(f, 'rule_id') for f in _findings(report)]}"
    )
    fail_hits = [f for f in hits if _get(f, "severity") == "fail"]
    assert fail_hits, f"R-LINT-006 finding(s) not fail severity: {[_get(f, 'severity') for f in hits]}"
    assert any("components/foo" in _file_str(f) for f in fail_hits), (
        f"R-LINT-006 finding does not point at the foo component: {[_file_str(f) for f in fail_hits]}"
    )

    hard_failures = _get(report, "hard_failures", None)
    if hard_failures is not None:
        assert hard_failures >= 1


def test_only_the_unsealed_unrealized_component_is_flagged(tmp_path):
    repo_root = tmp_path / "repo"
    _write_glossary(repo_root)
    _write_product(repo_root)
    # Offending: unsealed, zero realizes.
    _write_component(repo_root, "foo", "FOO", "sealed: false\n")
    # Control: sealed, exempt from realizes.
    _write_component(repo_root, "bar", "BAR", "sealed: true\nsource_path: legacy/bar\n")
    # Control: unsealed but realizes a real capability.
    _write_component(repo_root, "baz", "BAZ", "realizes: [P-FIXTURE]\n")

    report = spec_linter.lint(None, repo_root)

    hits = [f for f in _lint_006_findings(report) if _get(f, "severity") == "fail"]
    assert hits, "expected a fail-severity R-LINT-006 finding for comp-foo"
    files = [_file_str(f) for f in hits]
    assert any("components/foo" in p for p in files), files
    assert not any("components/bar" in p for p in files), (
        f"sealed component must not be flagged by R-LINT-006: {files}"
    )
    assert not any("components/baz" in p for p in files), (
        f"component with a realizes entry must not be flagged by R-LINT-006: {files}"
    )


def test_sealed_or_realizing_components_produce_no_r_lint_006(tmp_path):
    repo_root = tmp_path / "repo"
    _write_glossary(repo_root)
    _write_product(repo_root)
    _write_component(repo_root, "bar", "BAR", "sealed: true\nsource_path: legacy/bar\n")
    _write_component(repo_root, "baz", "BAZ", "sealed: false\nrealizes: [P-FIXTURE]\n")

    report = spec_linter.lint(None, repo_root)

    hits = _lint_006_findings(report)
    assert not hits, f"unexpected R-LINT-006 findings: {[(_file_str(f), _get(f, 'message')) for f in hits]}"


def test_cli_reports_r_lint_006_and_exits_1(tmp_path):
    repo_root = tmp_path / "repo"
    _write_glossary(repo_root)
    _write_component(repo_root, "foo", "FOO", "")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])

    assert code == 1, f"expected exit code 1 for a fail-severity finding, got {code}"
    payload = json.loads(buf.getvalue())
    findings = payload.get("findings", [])
    assert any(
        f.get("rule_id") == "R-LINT-006" and f.get("severity") == "fail"
        for f in findings
    ), f"no fail-severity R-LINT-006 in CLI JSON output: {findings}"