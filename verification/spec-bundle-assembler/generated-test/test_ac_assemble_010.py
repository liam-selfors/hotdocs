"""AC-ASSEMBLE-010: dependency_context carries only the dependency's Purpose.

Given a component that depends_on comp-bar, whose Purpose section reads
"Caches results." and whose Rationale section cites D13, when assemble runs
for the dependent component, then dependency_context["comp-bar"] is exactly
"Caches results." with no mention of D13 or any other Rationale content
anywhere in the assembled bundle.
"""

import json
from pathlib import Path

import spec_bundle_assembler


RATIONALE_SENTINEL = "Rationale-only sentinel phrase zqxv"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_component(
    specs: Path,
    slug: str,
    upper: str,
    depends_on: str,
    purpose: str,
    rationale: str,
) -> None:
    comp_dir = specs / "components" / slug
    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {slug.capitalize()} component\n"
        "status: draft\n"
        "owners: [tester]\n"
        f"depends_on: [{depends_on}]\n"
        "sealed: true\n"
        f"source_path: legacy/fake-{slug}\n"
        "---\n"
        "\n"
        f"# comp-{slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"{purpose}\n"
        "\n"
        "## Rationale\n"
        "\n"
        f"{rationale}\n",
    )
    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n"
        "\n"
        f"**R-{upper}-001** — The component MUST expose its documented "
        "library function.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the component\n"
        "When its library function is called\n"
        "Then it returns a value\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        f"run_{slug}() -> str\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "No special constraints.\n",
    )


def _build_fixture(repo_root: Path) -> None:
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "---\n"
        "id: glossary\n"
        "title: Glossary\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        "# Glossary\n"
        "\n"
        "- **Widget** — a thing the fixture components talk about.\n",
    )
    _write(
        specs / "decisions" / "D13.md",
        "---\n"
        "id: D13\n"
        "title: Use an in-memory cache\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n"
        "\n"
        "# D13\n"
        "\n"
        "We cache results in memory.\n",
    )
    _build_component(
        specs,
        slug="bar",
        upper="BAR",
        depends_on="",
        purpose="Caches results.",
        rationale=f"Chosen per D13. {RATIONALE_SENTINEL}.",
    )
    _build_component(
        specs,
        slug="foo",
        upper="FOO",
        depends_on="comp-bar",
        purpose="Uses cached results.",
        rationale="Kept deliberately simple.",
    )


def _hard_fail_findings(report):
    findings = _get(report, "findings", None)
    if findings is None and isinstance(report, (list, tuple)):
        findings = report
    hard = []
    for finding in findings or []:
        severity = str(
            _get(finding, "severity", None) or _get(finding, "level", "") or ""
        ).lower()
        if severity in ("hard-fail", "hard_fail", "hard", "error", "fail"):
            hard.append(finding)
    return hard


def _assert_lint_clean(repo_root: Path) -> None:
    try:
        from spec_linter import lint
    except ImportError:
        return
    report = lint(None, repo_root)
    hard = _hard_fail_findings(report)
    assert hard == [], f"fixture is not lint-clean: {hard!r}"


def _bundle_text(bundle) -> str:
    fields = [
        "component_id",
        "spec_bundle_hash",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
        "hint_code",
    ]
    parts = {name: _get(bundle, name) for name in fields}
    if isinstance(bundle, dict):
        parts.update(bundle)
    return json.dumps(parts, default=str, sort_keys=True)


def test_ac_assemble_010(tmp_path):
    repo_root = tmp_path / "repo"
    _build_fixture(repo_root)
    _assert_lint_clean(repo_root)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

    dependency_context = _get(bundle, "dependency_context")
    assert dependency_context is not None
    assert "comp-bar" in dependency_context
    bar_context = dependency_context["comp-bar"]
    assert isinstance(bar_context, str)
    assert bar_context.strip() == "Caches results."

    text = _bundle_text(bundle)
    assert "D13" not in text
    assert RATIONALE_SENTINEL not in text
    assert "Chosen per" not in text