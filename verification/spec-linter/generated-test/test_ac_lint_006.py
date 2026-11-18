# hotdocs-criterion: sha256:d516809a8bcf9286c75d36dde92f2bacdd1457f33090ecbeea291f6aabff357c
"""AC-LINT-006: a non-sealed component with zero `realizes` entries fails R-LINT-006."""

import json
from pathlib import Path

import pytest

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _norm(value):
    return getattr(value, "value", value)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_BODY = (
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo does a small, well-defined thing for testing.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: foo things.\n"
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


def _build_corpus(root, extra_frontmatter_lines, with_product=False):
    fm = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
    )
    for line in extra_frontmatter_lines:
        fm = fm + line + "\n"
    fm = fm + "---\n"
    comp_dir = root / "specs" / "components" / "foo"
    _write(comp_dir / "component.md", fm + COMPONENT_BODY)
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST return 1.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When foo runs\n"
        "Then it returns 1\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    _write(
        root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    if with_product:
        _write(
            root / "specs" / "product" / "foo-cap.md",
            "---\n"
            "id: P-FOO\n"
            "title: Foo capability\n"
            "status: draft\n"
            "owners: [team-a]\n"
            "---\n"
            "# Foo capability\n"
            "\n"
            "## Purpose\n"
            "\n"
            "Provide foo.\n"
            "\n"
            "## Scope\n"
            "\n"
            "- foo\n"
            "\n"
            "### CS-FOO-001\n"
            "\n"
            "Covers: P-FOO\n"
            "Kind: compiled\n"
            "\n"
            "```gherkin\n"
            "Given the system\n"
            "When foo is used\n"
            "Then it works\n"
            "```\n",
        )
    return root


def _lint006(report, severity=None):
    out = []
    for f in field(report, "findings"):
        if field(f, "rule_id") != "R-LINT-006":
            continue
        if severity is not None and _norm(field(f, "severity")) != severity:
            continue
        out.append(f)
    return out


@pytest.mark.parametrize(
    "extra",
    [
        [],  # sealed absent, realizes absent
        ["sealed: false"],  # sealed false, realizes absent
        ["sealed: false", "realizes: []"],  # sealed false, empty realizes
        ["realizes: []"],  # sealed absent, empty realizes
    ],
    ids=["absent-absent", "false-absent", "false-empty", "absent-empty"],
)
def test_unsealed_component_without_realizes_fails_r_lint_006(tmp_path, extra):
    root = _build_corpus(tmp_path, extra)
    report = spec_linter.lint(None, root)
    fails = _lint006(report, "fail")
    assert fails, "expected a fail-severity R-LINT-006 finding, got: " + repr(
        field(report, "findings")
    )
    assert field(report, "hard_failures") >= 1


def test_sealed_component_without_realizes_has_no_r_lint_006(tmp_path):
    root = _build_corpus(tmp_path, ["sealed: true", "source_path: legacy/foo/"])
    report = spec_linter.lint(None, root)
    assert _lint006(report) == []


def test_unsealed_component_with_realizes_has_no_r_lint_006(tmp_path):
    root = _build_corpus(tmp_path, ["realizes: [P-FOO]"], with_product=True)
    report = spec_linter.lint(None, root)
    assert _lint006(report, "fail") == []


def test_cli_json_reports_r_lint_006_fail(tmp_path, capsys):
    root = _build_corpus(tmp_path, ["sealed: false"])
    code = spec_linter.main(["--format=json", "--repo-root=" + str(root)])
    out = capsys.readouterr().out
    data = json.loads(out)
    matches = [
        f
        for f in data["findings"]
        if f["rule_id"] == "R-LINT-006" and f["severity"] == "fail"
    ]
    assert matches, "expected R-LINT-006 fail in JSON report: " + repr(data)
    assert data["summary"]["hard_failures"] >= 1
    assert code == 1