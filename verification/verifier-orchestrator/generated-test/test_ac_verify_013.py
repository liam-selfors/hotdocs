# hotdocs-criterion: sha256:11172d0fbb864ab78678f1166b06e1a64795be2e5fc5d996643385ac74875160
import importlib.util
import sys
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Widget** — a test term.\n"

PRODUCT = (
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
    "Widgets can be made.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: making widgets.\n"
    "\n"
    "### CS-WIDGET-001\n"
    "\n"
    "Covers: P-WIDGET\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a size is 1\n"
    "When make_widget is invoked with {\"x\": size}\n"
    "Then foo equals 5\n"
    "```\n"
)

COMPONENT = (
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
    "Widget makes widgets.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: making widgets.\n"
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
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** — `make_widget(x)` MUST return a value whose `foo` is `5`.\n"
)

ACCEPTANCE = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a size is 1\n"
    "When make_widget is invoked with {\"x\": size}\n"
    "Then foo equals 5\n"
    "```\n"
)

LIBRARY = (
    "# Library\n"
    "\n"
    "```\n"
    "make_widget(x: int) -> object\n"
    "```\n"
)

CONSTRAINTS = "# Constraints\n\nNone.\n"

GEN_CODE = (
    "import types\n"
    "\n"
    "\n"
    "def make_widget(x):\n"
    "    return types.SimpleNamespace(foo=3)\n"
)


def assembler_source(log_path):
    return (
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(criterion_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-WIDGET-001',\n"
        "        'criterion_text': " + repr(ACCEPTANCE) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT) + ",\n"
        "        'interface': " + repr(LIBRARY) + ",\n"
        "        'glossary': " + repr(GLOSSARY) + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    write(repo_root / "specs" / "product" / "widget.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "widget"
    write(comp / "component.md", COMPONENT)
    write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT)
    write(comp / "acceptance" / "AC-WIDGET-001.md", ACCEPTANCE)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "constraints.md", CONSTRAINTS)
    write(repo_root / "gen" / "widget" / "widget.py", GEN_CODE)
    log_path = repo_root.parent / "assembler_calls.log"
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(log_path),
    )


def test_compiled_equality_failure_carries_expected_and_actual(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = verifier_orchestrator.verify("comp-widget", repo_root)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-WIDGET-001"]
    assert len(matching) == 1, criteria
    criterion = matching[0]

    assert field(criterion, "result") == "fail", criterion

    detail = field(criterion, "failure_detail")
    assert detail is not None, criterion

    expected = field(detail, "expected")
    actual = field(detail, "actual")

    assert expected == 5, detail
    assert type(expected) is int, detail
    assert actual == 3, detail
    assert type(actual) is int, detail

    message = field(detail, "message")
    assert isinstance(message, str) and message.strip(), detail