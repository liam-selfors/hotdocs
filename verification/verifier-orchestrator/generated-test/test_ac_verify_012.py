# hotdocs-criterion: sha256:d032c613d06c2c2f37d5c36def981d48205e4fac1c7f494519ba8e528349ac72
import importlib.util
import sys
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
        "Renders widgets.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: rendering.\n"
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
        "**R-WIDGET-001** — The widget spec MUST be clear and unambiguous.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the widget spec\n"
        "When a reviewer reads it\n"
        "Then it is clear and unambiguous\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "render_widget(name: str) -> str\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
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
        "Widgets.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")
    write(repo_root / "gen" / "widget" / "widget.py", "")

    bundle_literal = {
        "component_id": "comp-widget",
        "criterion_id": "AC-WIDGET-001",
        "covers": "R-WIDGET-001",
        "criterion_text": "Given the widget spec\nWhen a reviewer reads it\nThen it is clear and unambiguous",
        "requirement_text": "**R-WIDGET-001** — The widget spec MUST be clear and unambiguous.",
        "interface": "render_widget(name: str) -> str",
        "glossary": "# Glossary",
        "dependency_interfaces": {},
        "testing": "",
    }
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    bundle = dict(" + repr(bundle_literal) + ")\n"
        "    bundle['component_id'] = component_id\n"
        "    bundle['criterion_id'] = criterion_id\n"
        "    return bundle\n",
    )
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return _Report()\n",
    )


def test_llm_judge_called_exactly_once(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    log = tmp_path / "judge_calls.log"

    def judge(bundle):
        with open(log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {"result": "pass", "rationale": "clear enough"}

    report = verifier_orchestrator.verify("comp-widget", repo_root, judge=judge)

    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    assert len(calls) == 1, "judge called " + str(len(calls)) + " times"

    criteria = field(report, "criteria")
    ids = [field(c, "id") for c in criteria]
    assert "AC-WIDGET-001" in ids