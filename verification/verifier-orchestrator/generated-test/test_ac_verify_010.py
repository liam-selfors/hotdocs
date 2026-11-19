# hotdocs-criterion: sha256:6432d1d3926491dcad8320a48ce0211ad41ca1d218281b37f68ff36b7ff97695
import importlib.util
import sys
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERION_TEXT = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When widget_double(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

REQUIREMENT_TEXT = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** \u2014 `widget_double(x)` MUST return `2 * x`.\n"
)

INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "widget_double(x: int) -> int\n"
    "```\n"
)


def build_fixture(repo_root, log_path):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** \u2014 a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets double numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- Doubling.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When widget_double(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
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
    write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_TEXT)
    write(comp / "acceptance" / "AC-WIDGET-001.md", CRITERION_TEXT)
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # The component's own (empty) code.
    write(repo_root / "gen" / "widget" / "widget.py", "")

    # Fake spec-bundle-assembler, matching its documented signature and
    # returning every CriterionBundle field.
    assembler_src = (
        "from pathlib import Path\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "CRITERION_TEXT = " + repr(CRITERION_TEXT) + "\n"
        "REQUIREMENT_TEXT = " + repr(REQUIREMENT_TEXT) + "\n"
        "INTERFACE_TEXT = " + repr(INTERFACE_TEXT) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('assemble_criterion ' + str(component_id) + ' ' + str(criterion_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-WIDGET-001',\n"
        "        'criterion_text': CRITERION_TEXT,\n"
        "        'requirement_text': REQUIREMENT_TEXT,\n"
        "        'interface': INTERFACE_TEXT,\n"
        "        'glossary': '# Glossary',\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_src,
    )


def test_generated_test_without_cache_or_author_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    build_fixture(repo_root, log_path)

    # No cached generated test exists.
    assert not (
        repo_root / "verification" / "widget" / "generated-test" / "test_ac_widget_001.py"
    ).exists()

    report = verifier_orchestrator.verify("comp-widget", repo_root)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-WIDGET-001"]
    assert len(matching) == 1
    entry = matching[0]

    assert field(entry, "result") != "skipped"
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "test"

    assert field(report, "overall") == "fail"