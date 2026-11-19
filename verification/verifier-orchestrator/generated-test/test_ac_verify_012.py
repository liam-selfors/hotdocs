# hotdocs-criterion: sha256:590cee13fb5272544f5b437fdbba064327f47ee7a9c59a50552e814a14200300
import os
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, assembler_log):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )

    write(
        repo_root / "specs" / "product" / "widget-capability.md",
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
        "Given a number is 2\n"
        "When the widget doubles it\n"
        "Then the answer is 4\n"
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
        "- Initial draft.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n"
        "**R-WIDGET-001** — `bar(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the widget specification\n"
        "When a reviewer reads requirement R-WIDGET-001\n"
        "Then it states the doubling behavior unambiguously\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nbar(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        repo_root / "gen" / "widget" / "widget.py",
        "def bar(x):\n    return 2 * x\n",
    )

    assembler_source = (
        "LOG_PATH = " + repr(str(assembler_log)) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(criterion_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-WIDGET-001',\n"
        "        'criterion_text': " + repr(
            "Given the widget specification\n"
            "When a reviewer reads requirement R-WIDGET-001\n"
            "Then it states the doubling behavior unambiguously"
        ) + ",\n"
        "        'requirement_text': " + repr(
            "**R-WIDGET-001** — `bar(x)` MUST return `2 * x`."
        ) + ",\n"
        "        'interface': " + repr("# Library\n\n```\nbar(x: int) -> int\n```") + ",\n"
        "        'glossary': " + repr("# Glossary\n\n- **Widget** — a test term.") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )


def test_llm_judge_called_exactly_once(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    judge_log = logs / "judge.log"

    build_fixture(repo_root, assembler_log)

    def judge(bundle):
        with open(judge_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        return {"result": "pass", "rationale": "The requirement is clear."}

    report = verifier_orchestrator.verify("comp-widget", repo_root, judge=judge)

    calls = []
    if judge_log.exists():
        calls = [line for line in judge_log.read_text(encoding="utf-8").splitlines() if line]

    assert len(calls) == 1, "judge called " + str(len(calls)) + " times, expected exactly 1"

    criteria = field(report, "criteria")
    ids = [field(c, "id") for c in criteria]
    assert "AC-WIDGET-001" in ids