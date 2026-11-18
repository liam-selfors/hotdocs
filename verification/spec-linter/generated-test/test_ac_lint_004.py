# hotdocs-criterion: sha256:62c2a8b21f3f6ebe8d5bdc55cfcd80f469e4d074f543e01fe7e9a355d088a3a9
import json
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


def _component_md(slug: str, depends_on: list) -> str:
    deps = ", ".join(depends_on)
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} Component\n"
        "status: draft\n"
        "owners: [alice]\n"
        f"depends_on: [{deps}]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}\n"
        "---\n"
        "\n"
        f"# {slug.capitalize()} Component\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Provides the {slug} behavior for test fixtures.\n"
        "\n"
        "## Scope\n"
        "\n"
        f"- In scope: {slug} behavior.\n"
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


def _make_component(repo_root: Path, slug: str, depends_on: list) -> None:
    upper = slug.upper()
    base = repo_root / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug, depends_on))
    _write(
        base / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n**R-{upper}-001** — The component MUST behave "
        "as its existing legacy code does.\n",
    )
    _write(
        base / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\nCovers: R-{upper}-001\nKind: compiled\n\n"
        "```gherkin\nGiven the legacy component\nWhen it runs\n"
        "Then it behaves as before\n```\n",
    )
    _write(
        base / "constraints.md",
        "# Constraints\n\nNone beyond existing legacy behavior.\n",
    )


def _build_corpus(repo_root: Path, alpha_deps: list, beta_deps: list) -> None:
    (repo_root / "specs" / "product").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "architecture").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "vars").mkdir(parents=True, exist_ok=True)
    (repo_root / "specs" / "decisions").mkdir(parents=True, exist_ok=True)
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Fixture term** — a term used only in tests.\n",
    )
    _make_component(repo_root, "alpha", alpha_deps)
    _make_component(repo_root, "beta", beta_deps)


def _findings(report):
    findings = _get(report, "findings", None)
    if findings is None:
        return []
    return list(findings)


def _lint_004_fail_findings(report):
    out = []
    for f in _findings(report):
        if _get(f, "rule_id") == "R-LINT-004" and _get(f, "severity") == "fail":
            out.append(f)
    return out


def _finding_text(f) -> str:
    message = _get(f, "message") or ""
    file_ = _get(f, "file") or ""
    return f"{message} {file_}"


def test_cycle_between_two_components_reports_fail_naming_both(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, ["comp-beta"], ["comp-alpha"])

    report = spec_linter.lint(None, repo_root)

    cycle_findings = _lint_004_fail_findings(report)
    assert cycle_findings, (
        "expected a fail-severity R-LINT-004 finding for the depends_on "
        f"cycle, got findings: {_findings(report)!r}"
    )

    naming_both = [
        f
        for f in cycle_findings
        if "comp-alpha" in _finding_text(f) and "comp-beta" in _finding_text(f)
    ]
    assert naming_both, (
        "expected an R-LINT-004 finding naming both comp-alpha and comp-beta, "
        f"got: {cycle_findings!r}"
    )

    hard_failures = _get(report, "hard_failures")
    if hard_failures is None:
        summary = _get(report, "summary")
        if summary is not None:
            hard_failures = _get(summary, "hard_failures")
    if hard_failures is not None:
        assert hard_failures >= 1


def test_acyclic_dependency_reports_no_cycle_finding(tmp_path):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, ["comp-beta"], [])

    report = spec_linter.lint(None, repo_root)

    lint_004 = [f for f in _findings(report) if _get(f, "rule_id") == "R-LINT-004"]
    assert not lint_004, (
        f"expected no R-LINT-004 finding for an acyclic graph, got: {lint_004!r}"
    )


def test_cycle_report_json_and_cli_exit_code(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    _build_corpus(repo_root, ["comp-beta"], ["comp-alpha"])

    report = spec_linter.lint(None, repo_root)
    to_json = getattr(report, "to_json", None)
    if callable(to_json):
        data = to_json()
        if isinstance(data, str):
            data = json.loads(data)
        json_findings = data.get("findings", [])
        matching = [
            f
            for f in json_findings
            if f.get("rule_id") == "R-LINT-004"
            and f.get("severity") == "fail"
            and "comp-alpha" in f"{f.get('message', '')} {f.get('file', '')}"
            and "comp-beta" in f"{f.get('message', '')} {f.get('file', '')}"
        ]
        assert matching, f"to_json() lacks the cycle finding: {data!r}"

    code = spec_linter.main([f"--repo-root={repo_root}", "--format=json"])
    capsys.readouterr()
    assert code == 1