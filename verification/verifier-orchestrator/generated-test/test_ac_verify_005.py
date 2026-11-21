# hotdocs-criterion: sha256:baab1b290cac719511f31d70660112e6d1194c2d851c72223501dde89d40d2ee
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


ASSEMBLER_SOURCE = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    covers = {'AC-WIDGET-001': 'R-WIDGET-001', 'AC-WIDGET-002': 'R-WIDGET-002'}.get(criterion_id, '')\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': covers,\n"
    "        'criterion_text': 'criterion ' + criterion_id,\n"
    "        'requirement_text': 'requirement ' + covers,\n"
    "        'interface': 'double_it(x: int) -> int',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
)

PROBE_SOURCE = (
    "class ProbeReport:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "        self.tests_run = 1\n"
    "        self.tests_reached = 1\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'ok': self.ok, 'findings': list(self.findings),\n"
    "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
    "\n"
    "\n"
    "GATE_VERSION = 'test-probe@1.3.0'\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
    "    return ProbeReport()\n"
)

WIDGET_SOURCE = (
    "def double_it(x):\n"
    "    return x * 2\n"
)

GENERATED_TEST_SOURCE = (
    "import widget\n"
    "\n"
    "\n"
    "def test_double_it():\n"
    "    assert widget.double_it(3) == 6\n"
)


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubles numbers.\n"
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
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubling.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "**R-WIDGET-001** — `double_it(x)` MUST return `x * 2`.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-002.md",
        "**R-WIDGET-002** — The widget docs MUST be clear.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "double_it(x: int) -> int\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a number 3\n"
        "When double_it is called with it\n"
        "Then the result is 6\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-002.md",
        "# AC-WIDGET-002\n"
        "\n"
        "Covers: R-WIDGET-002\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the widget docs\n"
        "When a reader reads them\n"
        "Then they are clear\n"
        "```\n",
    )
    write(repo_root / "gen" / "widget" / "widget.py", WIDGET_SOURCE)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_SOURCE,
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)


def make_test_author(log_path):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": "comp-widget",
            "criterion_id": "AC-WIDGET-001",
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": GENERATED_TEST_SOURCE,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author


def test_skipped_llm_judge_alone_does_not_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        "comp-widget", repo_root, judge=None, test_author=make_test_author(log_path)
    )

    criteria = {field(c, "id"): c for c in field(report, "criteria")}

    # Given: every generated-test criterion passes, the llm-judge one is skipped
    assert field(criteria["AC-WIDGET-001"], "kind") == "generated-test"
    assert field(criteria["AC-WIDGET-001"], "result") == "pass", criteria["AC-WIDGET-001"]
    assert field(criteria["AC-WIDGET-002"], "kind") == "llm-judge"
    assert field(criteria["AC-WIDGET-002"], "result") == "skipped"
    for c in criteria.values():
        if field(c, "kind") in ("compiled", "generated-test"):
            assert field(c, "result") == "pass", c
    # Given: every mutant killed, no interface drift
    assert field(report, "mutation_score") == 1.0, field(report, "mutation_error")
    assert field(report, "interface_drift") is False

    # Then: overall verdict is pass
    assert field(report, "overall") == "pass"

    as_dict = report.to_dict()
    assert as_dict["overall"] == "pass"
    json.dumps(as_dict)