# hotdocs-criterion: sha256:6432d1d3926491dcad8320a48ce0211ad41ca1d218281b37f68ff36b7ff97695
import sys
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODULE = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, log_path):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )

    write(
        repo_root / "specs" / "product" / "widgeting.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widgeting\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widgeting\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets double numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "\n"
        "```gherkin\n"
        "Given a number is 2\n"
        "When double is invoked with [2]\n"
        "Then result equals 4\n"
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
    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# R-WIDGET-001\n\n**R-WIDGET-001** — `double(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When double(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        repo_root / "gen" / SLUG / (MODULE + ".py"),
        "def double(x):\n    return 2 * x\n",
    )

    criterion_text = (
        "Given x = 2\n"
        "When double(x) is called\n"
        "Then it returns 4"
    )
    requirement_text = "**R-WIDGET-001** — `double(x)` MUST return `2 * x`."
    interface_text = "# Library\n\n```\ndouble(x: int) -> int\n```"
    glossary_text = "# Glossary\n\n- **Widget** — a test term."

    assembler_source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('assemble_criterion ' + str(component_id) + ' ' + str(criterion_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': " + repr(criterion_text) + ",\n"
        "        'requirement_text': " + repr(requirement_text) + ",\n"
        "        'interface': " + repr(interface_text) + ",\n"
        "        'glossary': " + repr(glossary_text) + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )


def find_criterion(report, criterion_id):
    for c in field(report, "criteria"):
        if field(c, "id") == criterion_id:
            return c
    raise AssertionError("criterion " + criterion_id + " not in report")


def test_generated_test_without_cache_or_author_is_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    build_fixture(repo_root, log_path)

    cached = (
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py"
    )
    assert not cached.exists()

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    criterion = find_criterion(report, CRITERION_ID)
    assert field(criterion, "kind") == "generated-test"
    assert field(criterion, "result") != "skipped"
    assert field(criterion, "result") == "fail"
    assert criterion.get("failure_origin") == "test"
    assert "test_authoring" not in criterion
    assert field(report, "overall") == "fail"

    as_dict = report.to_dict()
    dict_criterion = next(c for c in as_dict["criteria"] if c["id"] == CRITERION_ID)
    assert dict_criterion["result"] == "fail"
    assert as_dict["overall"] == "fail"