"""AC-VERIFY-004: interface drift between gen/<component>/ and interface/ is a hard failure.

Given a component whose gen/<component>/ public interface does not match
its interface/ contract, when verify runs, then interface_drift is true
and the overall verdict is fail.
"""

from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-widget-calc"
SLUG = "widget-calc"
MODULE_NAME = "widget_calc"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Widget** — a test term.\n"

PRODUCT = (
    "---\n"
    "id: P-WIDGET-SCALING\n"
    "title: Widget Scaling\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Widget Scaling\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Scale widget amounts by a factor.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: scaling amounts.\n"
    "- Out of scope: everything else.\n"
    "\n"
    "## Capability scenarios\n"
    "\n"
    "### CS-WIDGET-SCALING-001\n"
    "\n"
    "Covers: P-WIDGET-SCALING\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given a widget amount of 3\n"
    "When it is scaled by a factor of 2\n"
    "Then the scaled amount is 6\n"
    "```\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-widget-calc\n"
    "title: Widget Calc\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "realizes: [P-WIDGET-SCALING]\n"
    "---\n"
    "\n"
    "# Widget Calc\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Widget Calc scales an amount by a factor.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: scaling an amount.\n"
    "- Out of scope: anything else.\n"
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

REQUIREMENT = (
    "# R-WCALC-001\n"
    "\n"
    "**R-WCALC-001** — `scale_value(amount, factor)` MUST return `amount * factor`.\n"
)

ACCEPTANCE = (
    "# AC-WCALC-001\n"
    "\n"
    "Covers: R-WCALC-001\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given the widget calc specification\n"
    "When a reviewer reads its scaling requirement\n"
    "Then the requirement states the result is amount times factor\n"
    "```\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "scale_value(amount: int, factor: int) -> int\n"
    "```\n"
)

CONSTRAINTS = "# Constraints\n\nNone.\n"


def _build_fixture(repo_root: Path, gen_source: str) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "widget-scaling.md", PRODUCT)
    comp = repo_root / "specs" / "components" / SLUG
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-WCALC-001.md", REQUIREMENT)
    _write(comp / "acceptance" / "AC-WCALC-001.md", ACCEPTANCE)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "gen" / SLUG / f"{MODULE_NAME}.py", gen_source)


PARAMETER_MISMATCH = (
    "def scale_value(amount):\n"
    "    return amount * 2\n"
)

MISSING_CALLABLE = (
    "def unrelated_value(amount, factor):\n"
    "    return amount * factor\n"
)

MATCHING_WITH_EXTRA_PUBLIC_NAMES = (
    "from dataclasses import dataclass\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class ScaleResult:\n"
    "    value: int\n"
    "\n"
    "\n"
    "def scale_value(amount, factor):\n"
    "    return amount * factor\n"
    "\n"
    "\n"
    "def helper_describe(amount):\n"
    "    return str(amount)\n"
)


@pytest.mark.parametrize(
    "gen_source",
    [PARAMETER_MISMATCH, MISSING_CALLABLE],
    ids=["parameter-mismatch", "missing-callable"],
)
def test_interface_drift_is_hard_failure(tmp_path, gen_source):
    repo_root = tmp_path / "repo"
    _build_fixture(repo_root, gen_source)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"

    as_dict = report.to_dict() if hasattr(report, "to_dict") else report
    assert as_dict["interface_drift"] is True
    assert as_dict["overall"] == "fail"


def test_matching_interface_with_extra_public_names_is_not_drift(tmp_path):
    # Control: the same fixture with a gen/ module that matches interface/
    # (plus undocumented extra public names, which are not drift per D84)
    # must not report interface drift, so the failures above are attributable
    # to the drift itself.
    repo_root = tmp_path / "repo"
    _build_fixture(repo_root, MATCHING_WITH_EXTRA_PUBLIC_NAMES)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    assert field(report, "interface_drift") is False