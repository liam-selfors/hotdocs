# hotdocs-criterion: sha256:82543183eabc30fdcbbc606c36aa77bbeae2686e881bff0704c931d19bc4c1fc
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERION_GT_TEXT = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given the widget module exists\n"
    "When it is imported\n"
    "Then the import succeeds\n"
    "```\n"
)

CRITERION_JUDGE_TEXT = (
    "# AC-WIDGET-002\n"
    "\n"
    "Covers: R-WIDGET-002\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given the widget spec\n"
    "When a reviewer reads it\n"
    "Then it is free of contradiction\n"
    "```\n"
)

REQ_1_TEXT = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** — The `widget` module MUST be importable.\n"
)

REQ_2_TEXT = (
    "# R-WIDGET-002\n"
    "\n"
    "**R-WIDGET-002** — The widget spec MUST be free of contradiction.\n"
)


def build_fixture(repo_root, log_path):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provide a widget.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n",
    )
    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
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
        "Widget is an importable module.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: being importable.\n"
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
    write(comp / "requirements" / "R-WIDGET-001.md", REQ_1_TEXT)
    write(comp / "requirements" / "R-WIDGET-002.md", REQ_2_TEXT)
    write(comp / "acceptance" / "AC-WIDGET-001.md", CRITERION_GT_TEXT)
    write(comp / "acceptance" / "AC-WIDGET-002.md", CRITERION_JUDGE_TEXT)
    write(comp / "interface" / "library.md", "# Library\n\nNone.\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # Empty generated module: no mutants, so the mutation score is 1.0.
    write(repo_root / "gen" / "widget" / "widget.py", "")

    texts = {
        "AC-WIDGET-001": (CRITERION_GT_TEXT, "R-WIDGET-001", REQ_1_TEXT),
        "AC-WIDGET-002": (CRITERION_JUDGE_TEXT, "R-WIDGET-002", REQ_2_TEXT),
    }
    assembler_source = (
        "import json\n"
        "\n"
        "TEXTS = json.loads(" + repr(json.dumps(texts)) + ")\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('assemble_criterion ' + criterion_id + '\\n')\n"
        "    criterion_text, covers, requirement_text = TEXTS[criterion_id]\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': covers,\n"
        "        'criterion_text': criterion_text,\n"
        "        'requirement_text': requirement_text,\n"
        "        'interface': '# Library\\n\\nNone.',\n"
        "        'glossary': '# Glossary\\n\\n- **Widget** — a test term.',\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )


GENERATED_TEST_CONTENT = (
    "import widget\n"
    "\n"
    "\n"
    "def test_widget_imports():\n"
    "    assert widget is not None\n"
)


def make_test_author(log_path):
    def author(bundle):
        criterion_id = field(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("test_author " + str(criterion_id) + "\n")
        return {
            "component_id": "comp-widget",
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": GENERATED_TEST_CONTENT,
            },
        }

    return author


def test_skipped_llm_judge_alone_does_not_fail_overall(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    build_fixture(repo_root, log_path)

    report = verifier_orchestrator.verify(
        "comp-widget", repo_root, test_author=make_test_author(log_path)
    )

    criteria = {field(c, "id"): c for c in field(report, "criteria")}

    # Preconditions of the Given clause.
    assert field(criteria["AC-WIDGET-001"], "kind") == "generated-test"
    assert field(criteria["AC-WIDGET-001"], "result") == "pass"
    assert field(criteria["AC-WIDGET-002"], "kind") == "llm-judge"
    assert field(criteria["AC-WIDGET-002"], "result") == "skipped"
    for c in criteria.values():
        if field(c, "kind") in ("compiled", "generated-test"):
            assert field(c, "result") == "pass"
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") == 1.0

    assert "test_author AC-WIDGET-001" in log_path.read_text(encoding="utf-8")

    # Then: the overall verdict is pass.
    assert field(report, "overall") == "pass"