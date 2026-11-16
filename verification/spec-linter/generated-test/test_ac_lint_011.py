"""AC-LINT-011 (Covers: R-LINT-011).

Given a component's Definitions section whose entry for a glossary term is a
near-verbatim copy (token-overlap ratio >= 0.8) of that term's definition in
specs/glossary.md, when hotdocs lint runs against the component, then the
report contains a fail-severity finding for rule R-LINT-011.
"""

import json
from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GLOSSARY_TERM = "Widget frame"

GLOSSARY_DEFINITION = (
    "the fixed rectangular container that every widget renders inside, "
    "sized by its parent layout and never resized by the widget itself "
    "once the first paint has completed on screen."
)

# Near-verbatim copy: one token changed ("fixed" -> "static") out of ~30,
# so any normalized token-overlap ratio stays well above 0.8.
NEAR_VERBATIM_LOCAL = (
    "the static rectangular container that every widget renders inside, "
    "sized by its parent layout and never resized by the widget itself "
    "once the first paint has completed on screen."
)

# A genuine delta: shares almost no tokens with the glossary definition.
GENUINE_DELTA_LOCAL = (
    "Here, additionally carries a numeric z-order used when two overlapping "
    "panes compete for keyboard focus during drag operations."
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root: Path, local_definition: str) -> Path:
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this test corpus.\n"
        "\n"
        f"- **{GLOSSARY_TERM}** — {GLOSSARY_DEFINITION}\n"
        "- **Other term** — an unrelated entry that exists only so the "
        "glossary has more than one term in it.\n",
    )

    comp_dir = specs / "components" / "widget"
    component_md = comp_dir / "component.md"
    _write(
        component_md,
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        "source_path: legacy/widget/\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Renders a widget inside its frame.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: rendering a widget.\n"
        "- Out of scope: layout.\n"
        "\n"
        "## Definitions\n"
        "\n"
        f"- **{GLOSSARY_TERM}** — {local_definition}\n"
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
        comp_dir / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** — The widget MUST render inside its frame.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it renders\n"
        "Then it renders inside its frame\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "- Rendering completes within 16 ms, measured by a benchmark.\n",
    )
    return component_md


def _lint_findings(repo_root: Path):
    report = spec_linter.lint(None, repo_root)
    return list(field(report, "findings"))


def _r_lint_011(findings):
    return [f for f in findings if field(f, "rule_id") == "R-LINT-011"]


def test_near_verbatim_definition_copy_is_fail_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, NEAR_VERBATIM_LOCAL)

    findings = _lint_findings(repo_root)
    matching = _r_lint_011(findings)

    assert matching, (
        "expected an R-LINT-011 finding; got: "
        + repr([(field(f, "rule_id"), field(f, "severity")) for f in findings])
    )
    assert any(field(f, "severity") == "fail" for f in matching), (
        "expected an R-LINT-011 finding with severity 'fail'; got severities "
        + repr([field(f, "severity") for f in matching])
    )


def test_exact_definition_copy_is_fail_finding(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, GLOSSARY_DEFINITION)

    matching = _r_lint_011(_lint_findings(repo_root))

    assert any(field(f, "severity") == "fail" for f in matching)


def test_genuine_delta_is_not_r_lint_011_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, GENUINE_DELTA_LOCAL)

    matching = _r_lint_011(_lint_findings(repo_root))

    assert not any(field(f, "severity") == "fail" for f in matching), (
        "a Definitions entry with low token overlap must not fail R-LINT-011"
    )


def test_cli_json_report_contains_r_lint_011_fail(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root, NEAR_VERBATIM_LOCAL)

    code = spec_linter.main(["--format=json", f"--repo-root={repo_root}"])
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    matching = [
        f for f in doc["findings"]
        if f["rule_id"] == "R-LINT-011" and f["severity"] == "fail"
    ]
    assert matching
    assert doc["summary"]["hard_failures"] >= 1