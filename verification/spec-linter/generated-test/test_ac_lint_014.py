import json
from pathlib import Path

import spec_linter


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_base_corpus(root: Path) -> None:
    comp = root / "specs" / "components" / "widget"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/widget\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides a widget for test purposes.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
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
        "- Initial draft.\n",
    )
    _write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — The widget MUST exist.\n",
    )
    _write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is checked\n"
        "Then it exists\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this spec corpus.\n"
        "\n"
        "- **Widget** — a thing the widget component provides.\n",
    )


def _add_second_glossary(root: Path) -> None:
    _write(
        root / "specs" / "glossary-billing.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this spec corpus.\n"
        "\n"
        "- **Invoice** — a billing document.\n",
    )


def _lint014_fail_findings(report):
    findings = _get(report, "findings", []) or []
    out = []
    for f in findings:
        if _get(f, "rule_id") == "R-LINT-014" and _get(f, "severity") == "fail":
            out.append(f)
    return out


def test_two_glossaries_without_bounded_context_decision_fails(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _build_base_corpus(root)
    _add_second_glossary(root)

    report = spec_linter.lint(None, root)

    hits = _lint014_fail_findings(report)
    assert hits, (
        "expected a fail-severity R-LINT-014 finding, got: "
        + repr(_get(report, "findings"))
    )
    hard_failures = _get(report, "hard_failures")
    if hard_failures is None:
        summary = _get(report, "summary")
        if summary is not None:
            hard_failures = _get(summary, "hard_failures")
    if hard_failures is not None:
        assert hard_failures >= 1


def test_single_glossary_has_no_lint014_failure(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _build_base_corpus(root)

    report = spec_linter.lint(None, root)

    hits = _lint014_fail_findings(report)
    assert not hits, "unexpected R-LINT-014 finding with one glossary: " + repr(hits)


def test_cli_reports_lint014_and_exits_one(tmp_path, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    _build_base_corpus(root)
    _add_second_glossary(root)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(root)])
    assert code == 1

    out = capsys.readouterr().out
    data = json.loads(out)
    findings = data.get("findings", []) if isinstance(data, dict) else []
    assert any(
        f.get("rule_id") == "R-LINT-014" and f.get("severity") == "fail"
        for f in findings
    ), "expected R-LINT-014 fail finding in JSON output: " + out