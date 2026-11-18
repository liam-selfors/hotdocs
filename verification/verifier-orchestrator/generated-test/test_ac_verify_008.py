# hotdocs-criterion: sha256:686b95bb0cb3e9f5d47eb7f4cf258cd69ba1bda01e7e10869277d725574d14f1
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERIA = {
    "AC-WIDGET-001": {
        "covers": "R-WIDGET-001",
        "criterion_text": "Given the widget spec\nWhen it is read\nThen it is clear",
        "requirement_text": "**R-WIDGET-001** — The widget spec MUST be clear.",
    },
    "AC-WIDGET-002": {
        "covers": "R-WIDGET-002",
        "criterion_text": "Given n = 2\nWhen make_widget(n) is called\nThen it returns 3",
        "requirement_text": "**R-WIDGET-002** — `make_widget(n)` MUST return `n + 1`.",
    },
}

INTERFACE_TEXT = "# Library\n\n```\nmake_widget(n: int) -> int\n```\n"


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** — a test term.\n")
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
        "Widgets exist.\n",
    )
    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGETS]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget increments a number.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n" + CRITERIA["AC-WIDGET-001"]["requirement_text"] + "\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-002.md",
        "# R-WIDGET-002\n\n" + CRITERIA["AC-WIDGET-002"]["requirement_text"] + "\n",
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
        "When it is read\n"
        "Then it is clear\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-002.md",
        "# AC-WIDGET-002\n"
        "\n"
        "Covers: R-WIDGET-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given n = 2\n"
        "When make_widget(n) is called\n"
        "Then it returns 3\n"
        "```\n",
    )
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # The component's own generated code (empty: the authored test imports nothing).
    write(repo_root / "gen" / "widget" / "widget.py", "")

    # Fake spec-bundle-assembler, flat-module shape.
    assembler_src = (
        "CRITERIA = " + repr(CRITERIA) + "\n"
        "INTERFACE_TEXT = " + repr(INTERFACE_TEXT) + "\n"
        "GLOSSARY_TEXT = " + repr("# Glossary\n\n- **Widget** — a test term.") + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    c = CRITERIA[criterion_id]\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': c['covers'],\n"
        "        'criterion_text': c['criterion_text'],\n"
        "        'requirement_text': c['requirement_text'],\n"
        "        'interface': INTERFACE_TEXT,\n"
        "        'glossary': GLOSSARY_TEXT,\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_src,
    )


def make_judge(log_path):
    def judge(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(field(bundle, "criterion_id")) + "\n")
        return {"result": "pass", "rationale": "consistent verdict"}

    return judge


def make_author(log_path):
    content = "def test_widget_ok():\n    assert 1 + 1 == 2\n"

    def author(bundle):
        criterion_id = field(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(criterion_id) + "\n")
        filename = "test_" + criterion_id.lower().replace("-", "_") + ".py"
        return {
            "component_id": field(bundle, "component_id"),
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/" + filename,
                "content": content,
            },
            "model_call_error": None,
        }

    return author


def test_verify_twice_yields_identical_reports(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    logs = tmp_path / "logs"
    logs.mkdir()
    judge = make_judge(logs / "judge.log")
    author = make_author(logs / "author.log")

    first = verifier_orchestrator.verify(
        "comp-widget", repo_root, judge=judge, test_author=author
    )
    second = verifier_orchestrator.verify(
        "comp-widget", repo_root, judge=judge, test_author=author
    )

    first_dict = first.to_dict()
    second_dict = second.to_dict()

    ids = [field(c, "id") for c in field(first, "criteria")]
    assert "AC-WIDGET-001" in ids
    assert "AC-WIDGET-002" in ids

    assert first_dict == second_dict
    assert json.dumps(first_dict, sort_keys=True, default=str) == json.dumps(
        second_dict, sort_keys=True, default=str
    )
    assert field(first, "overall") == field(second, "overall")
    assert field(first, "criteria") == field(second, "criteria")
    assert field(first, "requirement_results") == field(second, "requirement_results")
    assert first == second