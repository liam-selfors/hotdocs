# hotdocs-criterion: sha256:7270877e6a5a0a31f4d3c491ed5cffe22031d0717473ed835df7ca623fbe8a7c
# Test for AC-VERIFY-012 (covers R-VERIFY-003): an llm-judge-kind criterion
# invokes the injected judge exactly once.
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
        repo_root / "specs" / "product" / "widget-capability.md",
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
        "Widgets exist.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- Widgets.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "\n"
        "```gherkin\n"
        "Given a widget_input is 1\n"
        "When widget_size is invoked with [widget_input]\n"
        "Then result equals 1\n"
        "```\n",
    )

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
        "Computes the size of a widget.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widget sizes.\n"
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
        "**R-WIDGET-001** — The widget documentation MUST be clear.\n",
    )

    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "widget_size(x: int) -> int\n"
        "```\n",
    )

    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the widget documentation\n"
        "When a reviewer reads it\n"
        "Then it is clear\n"
        "```\n",
    )

    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    # The component's own (empty) code.
    write(repo_root / "gen" / "widget" / "widget.py", "")

    # Fake spec-bundle-assembler: assemble_criterion returns every
    # CriterionBundle key.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr("R-WIDGET-001") + ",\n"
        "        'criterion_text': " + repr("Given the widget documentation") + ",\n"
        "        'requirement_text': " + repr("The widget documentation MUST be clear.") + ",\n"
        "        'interface': " + repr("widget_size(x: int) -> int") + ",\n"
        "        'glossary': " + repr("# Glossary") + ",\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n",
    )

    # Fake test-probe: always ok, no findings.
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


def make_counting_judge(log_path):
    def judge(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {"result": "pass", "rationale": "clear enough"}

    return judge


def test_llm_judge_called_exactly_once(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    log_path = tmp_path / "judge_calls.log"
    judge = make_counting_judge(log_path)

    report = verifier_orchestrator.verify("comp-widget", repo_root, judge=judge)

    assert report is not None
    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert calls == ["called"], "judge was called " + str(len(calls)) + " times"