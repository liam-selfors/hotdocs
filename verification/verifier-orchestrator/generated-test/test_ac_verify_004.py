# hotdocs-criterion: sha256:28c2a3b3dd4873db11df990a47bf1fc496415763800cde7a80b33a6b5460ed66
"""AC-VERIFY-004: a component whose gen/<component>/ public interface does not
match its interface/ contract makes verify report interface_drift true and an
overall verdict of fail (R-VERIFY-004)."""

from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODULE_NAME = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"

GLOSSARY_TEXT = "# Glossary\n\n- **Widget** — a test term.\n"

LIBRARY_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "widget_double(x: int) -> int\n"
    "widget_label(name: str, prefix: str) -> str\n"
    "```\n"
)

REQUIREMENT_TEXT = (
    "# " + REQUIREMENT_ID + "\n"
    "\n"
    "**" + REQUIREMENT_ID + "** — `widget_double(x)` MUST return `2 * x`.\n"
)

CRITERION_TEXT = (
    "# " + CRITERION_ID + "\n"
    "\n"
    "Covers: " + REQUIREMENT_ID + "\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given a widget specification\n"
    "When a reviewer reads it\n"
    "Then the doubling behaviour is stated clearly\n"
    "```\n"
)

# Generated code variants.
MISSING_CALLABLE_SOURCE = (
    "def widget_label(name, prefix):\n"
    "    return prefix + name\n"
    "\n"
    "\n"
    "class WidgetHelper:\n"
    "    pass\n"
)

PARAMETER_MISMATCH_SOURCE = (
    "def widget_double(y, z):\n"
    "    return 2 * y\n"
    "\n"
    "\n"
    "def widget_label(name, prefix):\n"
    "    return prefix + name\n"
)

MATCHING_SOURCE = (
    "def widget_double(x):\n"
    "    return 2 * x\n"
    "\n"
    "\n"
    "def widget_label(name, prefix):\n"
    "    return prefix + name\n"
    "\n"
    "\n"
    "class WidgetHelper:\n"
    "    pass\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def fake_assembler_source():
    lines = [
        "def assemble_criterion(component_id, criterion_id, repo_root):",
        "    return {",
        "        'component_id': component_id,",
        "        'criterion_id': criterion_id,",
        "        'covers': " + repr(REQUIREMENT_ID) + ",",
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",",
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",",
        "        'interface': " + repr(LIBRARY_TEXT) + ",",
        "        'glossary': " + repr(GLOSSARY_TEXT) + ",",
        "        'dependency_interfaces': {},",
        "    }",
        "",
    ]
    return "\n".join(lines)


def build_fixture(repo_root, gen_source):
    specs = repo_root / "specs"
    write(specs / "glossary.md", GLOSSARY_TEXT)

    write(
        specs / "product" / "widget-capability.md",
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
        "Widgets double numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "\n"
        "```gherkin\n"
        "Given a number\n"
        "When it is doubled\n"
        "Then the result is twice the number\n"
        "```\n",
    )

    comp = specs / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget doubles a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
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
    write(comp / "requirements" / (REQUIREMENT_ID + ".md"), REQUIREMENT_TEXT)
    write(comp / "acceptance" / (CRITERION_ID + ".md"), CRITERION_TEXT)
    write(comp / "interface" / "library.md", LIBRARY_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # Fake spec-bundle-assembler at the path verify loads it from.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        fake_assembler_source(),
    )

    # The component's generated code.
    write(repo_root / "gen" / SLUG / (MODULE_NAME + ".py"), gen_source)


@pytest.mark.parametrize(
    "gen_source",
    [MISSING_CALLABLE_SOURCE, PARAMETER_MISMATCH_SOURCE],
    ids=["missing-callable", "parameter-mismatch"],
)
def test_interface_drift_fails_verdict(tmp_path, gen_source):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, gen_source)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"

    # The only criterion is an llm-judge with no judge: skipped, which never
    # fails overall by itself, so the fail verdict comes from the drift.
    criteria = field(report, "criteria")
    results = {c["id"]: c["result"] for c in criteria}
    assert results.get(CRITERION_ID) == "skipped"


def test_matching_interface_has_no_drift(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, MATCHING_SOURCE)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    assert field(report, "interface_drift") is False