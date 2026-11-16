import sys
from pathlib import Path

import spec_linter


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(comp_id, title, depends_on, depends_on_guarantees, source_path):
    lines = [
        "---",
        f"id: {comp_id}",
        f"title: {title}",
        "status: draft",
        "owners: [test-team]",
    ]
    if depends_on is not None:
        lines.append("depends_on: [" + ", ".join(depends_on) + "]")
    if depends_on_guarantees is not None:
        lines.append(
            "depends_on_guarantees: [" + ", ".join(depends_on_guarantees) + "]"
        )
    lines.append("sealed: true")
    lines.append(f"source_path: {source_path}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append(f"A small synthetic component named {title} used as a test fixture.")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append("- In scope: fixture behavior.")
    lines.append("- Out of scope: everything else.")
    lines.append("")
    lines.append("## Definitions")
    lines.append("")
    lines.append("None.")
    lines.append("")
    lines.append("## Behavior")
    lines.append("")
    lines.append("See `requirements/`.")
    lines.append("")
    lines.append("## Interfaces")
    lines.append("")
    lines.append("See `interface/`.")
    lines.append("")
    lines.append("## Data")
    lines.append("")
    lines.append("See `interface/data/`.")
    lines.append("")
    lines.append("## Acceptance criteria")
    lines.append("")
    lines.append("See `acceptance/`.")
    lines.append("")
    lines.append("## Non-functional constraints")
    lines.append("")
    lines.append("See `constraints.md`.")
    lines.append("")
    lines.append("## Open questions")
    lines.append("")
    lines.append("## Change log")
    lines.append("")
    lines.append("- Initial draft.")
    lines.append("")
    return "\n".join(lines)


def _requirement(req_id: str) -> str:
    return (
        f"# {req_id}\n"
        "\n"
        f"**{req_id}** — The component MUST behave as its fixture describes.\n"
    )


def _acceptance(ac_id: str, req_id: str) -> str:
    return (
        f"# {ac_id}\n"
        "\n"
        f"Covers: {req_id}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the fixture component\n"
        "When it runs\n"
        "Then it behaves as described\n"
        "```\n"
    )


def _constraints() -> str:
    return (
        "# Constraints\n"
        "\n"
        "- None beyond the defaults; measured by inspection.\n"
    )


def _build_corpus(repo_root: Path, foo_depends_on_bar: bool) -> None:
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Fixture** — a synthetic test corpus.\n",
    )

    # comp-bar: owns guarantee G-BAR-001
    bar = specs / "components" / "bar"
    _write(
        bar / "component.md",
        _component_md("comp-bar", "Bar", None, None, "legacy/bar"),
    )
    _write(bar / "requirements" / "R-BAR-001.md", _requirement("R-BAR-001"))
    _write(bar / "acceptance" / "AC-BAR-001.md", _acceptance("AC-BAR-001", "R-BAR-001"))
    _write(
        bar / "interface" / "guarantees" / "G-BAR-001.md",
        "# G-BAR-001\n\n**G-BAR-001** — Bar MUST return results in a stable order.\n",
    )
    _write(bar / "constraints.md", _constraints())

    # comp-foo: relies on G-BAR-001
    foo = specs / "components" / "foo"
    depends_on = ["comp-bar"] if foo_depends_on_bar else []
    _write(
        foo / "component.md",
        _component_md("comp-foo", "Foo", depends_on, ["G-BAR-001"], "legacy/foo"),
    )
    _write(foo / "requirements" / "R-FOO-001.md", _requirement("R-FOO-001"))
    _write(foo / "acceptance" / "AC-FOO-001.md", _acceptance("AC-FOO-001", "R-FOO-001"))
    _write(foo / "constraints.md", _constraints())


def _findings(report):
    findings = _get(report, "findings", None)
    assert findings is not None, "LintReport has no findings"
    return list(findings)


def _lint018_naming_bar(findings):
    out = []
    for f in findings:
        rule_id = _get(f, "rule_id")
        severity = _get(f, "severity")
        message = _get(f, "message") or ""
        if rule_id == "R-LINT-018" and severity == "fail" and "comp-bar" in message:
            out.append(f)
    return out


def test_ac_lint_018_missing_owning_dependency_is_reported(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, foo_depends_on_bar=False)

    report = spec_linter.lint(None, repo_root)
    findings = _findings(report)

    matches = _lint018_naming_bar(findings)
    assert matches, (
        "expected a fail-severity R-LINT-018 finding naming comp-bar; got: "
        + repr(
            [
                (_get(f, "rule_id"), _get(f, "severity"), _get(f, "message"))
                for f in findings
            ]
        )
    )

    hard_failures = _get(report, "hard_failures", None)
    if hard_failures is None:
        summary = _get(report, "summary", None)
        if summary is not None:
            hard_failures = _get(summary, "hard_failures", None)
    if hard_failures is not None:
        assert hard_failures >= 1


def test_ac_lint_018_no_finding_when_owner_is_listed_in_depends_on(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, foo_depends_on_bar=True)

    report = spec_linter.lint(None, repo_root)
    findings = _findings(report)

    matches = _lint018_naming_bar(findings)
    assert not matches, (
        "did not expect an R-LINT-018 finding naming comp-bar when comp-bar "
        "is in depends_on; got: "
        + repr([_get(f, "message") for f in matches])
    )

    lint018_fails = [
        f
        for f in findings
        if _get(f, "rule_id") == "R-LINT-018" and _get(f, "severity") == "fail"
    ]
    assert not lint018_fails, (
        "G-BAR-001 exists and its owner is depended upon; expected no "
        "R-LINT-018 failures, got: "
        + repr([_get(f, "message") for f in lint018_fails])
    )