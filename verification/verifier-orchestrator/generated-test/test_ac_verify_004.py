# hotdocs-criterion: sha256:28c2a3b3dd4873db11df990a47bf1fc496415763800cde7a80b33a6b5460ed66
import importlib.util
import sys
from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODULE = "widget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def assembler_source():
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr("R-WIDGET-001") + ",\n"
        "        'criterion_text': " + repr("Given a widget\nWhen it is scaled\nThen it is scaled") + ",\n"
        "        'requirement_text': " + repr("**R-WIDGET-001** - scale MUST multiply.") + ",\n"
        "        'interface': " + repr("# Library\n\nscale(value: int, factor: int) -> int") + ",\n"
        "        'glossary': " + repr("# Glossary\n\n- **Widget** - a test term.") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )


def build_fixture(repo_root, module_source):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** \u2014 a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "P-WIDGET.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget Capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget Capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Scale widgets.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- Scaling.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "\n"
        "```gherkin\n"
        "Given a widget is 2\n"
        "When scale is invoked with [2, 3]\n"
        "Then value equals 6\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGET]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget scales a number by a factor.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: scaling.\n"
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
        "- Initial.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** \u2014 `scale(value, factor)` MUST return `value * factor`.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the widget requirements\n"
        "When a reviewer reads them\n"
        "Then they are unambiguous\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nscale(value: int, factor: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), module_source)


MISSING_CALLABLE = (
    "def other(value, factor):\n"
    "    return value * factor\n"
)

PARAM_MISMATCH = (
    "def scale(value):\n"
    "    return value\n"
)

MATCHING = (
    "def scale(value, factor):\n"
    "    return value * factor\n"
)


@pytest.mark.parametrize(
    "module_source",
    [MISSING_CALLABLE, PARAM_MISMATCH],
    ids=["missing-callable", "parameter-mismatch"],
)
def test_interface_drift_fails_verification(tmp_path, module_source):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, module_source)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"

    as_dict = report.to_dict() if hasattr(report, "to_dict") else report
    assert as_dict["interface_drift"] is True
    assert as_dict["overall"] == "fail"


def test_matching_interface_reports_no_drift(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, MATCHING)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    assert field(report, "interface_drift") is False