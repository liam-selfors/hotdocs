# hotdocs-criterion: sha256:590cee13fb5272544f5b437fdbba064327f47ee7a9c59a50552e814a14200300
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERION_TEXT = (
    "Given a widget is 2\n"
    "When make_widget is invoked with [widget]\n"
    "Then the widget documentation is clear and unambiguous"
)
REQUIREMENT_TEXT = "**R-WIDGET-001** — The widget docs MUST be clear."


def build_fixture(repo_root, assembler_log):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "widgets.md",
        "---\n"
        "id: P-WIDGETS\n"
        "title: Widgets\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widgets\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Make widgets.\n",
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
        "realizes: [P-WIDGETS]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget doubles a number.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n" + REQUIREMENT_TEXT + "\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n" + CRITERION_TEXT + "\n```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nmake_widget(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        repo_root / "gen" / "widget" / "widget.py",
        "def make_widget(x):\n    return 2 * x\n",
    )

    bundle = {
        "component_id": "comp-widget",
        "criterion_id": "AC-WIDGET-001",
        "covers": "R-WIDGET-001",
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": "# Library\n\n```\nmake_widget(x: int) -> int\n```",
        "glossary": "# Glossary\n\n- **Widget** — a test term.",
        "dependency_interfaces": {},
    }
    source = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(assembler_log)) + "\n"
        "BUNDLE = json.loads(" + repr(json.dumps(bundle)) + ")\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(criterion_id) + '\\n')\n"
        "    result = dict(BUNDLE)\n"
        "    result['component_id'] = component_id\n"
        "    result['criterion_id'] = criterion_id\n"
        "    return result\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        source,
    )


def test_llm_judge_called_exactly_once(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    assembler_log = tmp_path / "assembler_calls.log"
    build_fixture(repo_root, assembler_log)

    calls = []

    def judge(bundle):
        calls.append(bundle)
        return {"result": "pass", "rationale": "clear enough"}

    report = verifier_orchestrator.verify("comp-widget", repo_root, judge=judge)

    # The judge was configured, so it must be called; and exactly once —
    # no second, disagreement-style call.
    assert len(calls) == 1, "judge called " + str(len(calls)) + " times"

    assert field(calls[0], "criterion_id") == "AC-WIDGET-001"

    criteria = field(report, "criteria")
    ids = [c["id"] for c in criteria]
    assert ids.count("AC-WIDGET-001") == 1