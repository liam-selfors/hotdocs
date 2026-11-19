# hotdocs-criterion: sha256:686b95bb0cb3e9f5d47eb7f4cf258cd69ba1bda01e7e10869277d725574d14f1
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def assembler_source(log_path):
    return (
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "TEXTS = {\n"
        "    'AC-WIDGET-001': ('Given a widget spec\\nWhen it is reviewed\\nThen it is clear',\n"
        "                      '**R-WIDGET-001** — The widget spec MUST be clear.'),\n"
        "    'AC-WIDGET-002': ('Given x = 3\\nWhen double_it(x) is called\\nThen it returns 6',\n"
        "                      '**R-WIDGET-002** — `double_it(x)` MUST return `2 * x`.'),\n"
        "}\n"
        "\n"
        "COVERS = {'AC-WIDGET-001': 'R-WIDGET-001', 'AC-WIDGET-002': 'R-WIDGET-002'}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(criterion_id) + '\\n')\n"
        "    criterion_text, requirement_text = TEXTS.get(criterion_id, ('', ''))\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': COVERS.get(criterion_id, ''),\n"
        "        'criterion_text': criterion_text,\n"
        "        'requirement_text': requirement_text,\n"
        "        'interface': '# Library\\n\\n```\\ndouble_it(x: int) -> int\\n```',\n"
        "        'glossary': '# Glossary\\n\\n- **Widget** — a test term.',\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )


def build_fixture(repo_root, assembler_log):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget-cap.md",
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
        "Doubles numbers.\n"
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
        "Given a x is 2\n"
        "When widget.double_it is invoked with [2]\n"
        "Then value equals 4\n"
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
        "realizes: [P-WIDGET]\n"
        "depends_on: []\n"
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
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — The widget spec MUST be clear.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-002.md",
        "# R-WIDGET-002\n\n**R-WIDGET-002** — `double_it(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a widget spec\n"
        "When it is reviewed\n"
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
        "Given x = 3\n"
        "When double_it(x) is called\n"
        "Then it returns 6\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble_it(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "gen" / "widget" / "widget.py",
        "def double_it(x):\n    return 2 * x\n",
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(assembler_log),
    )


def snapshot(root):
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts:
            out[str(p.relative_to(root))] = p.read_bytes()
    return out


def report_dict(report):
    if isinstance(report, dict):
        return report
    return report.to_dict()


def test_verify_twice_yields_identical_reports(tmp_path):
    repo_root = tmp_path / "repo"
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    judge_log = logs / "judge.log"
    author_log = logs / "author.log"
    build_fixture(repo_root, assembler_log)

    test_content = (
        "import widget\n"
        "\n"
        "\n"
        "def test_double_it():\n"
        "    assert widget.double_it(3) == 6\n"
    )

    def judge(bundle):
        with open(judge_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        return {"result": "pass", "rationale": "The criterion is satisfied."}

    def test_author(bundle):
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        return {
            "component_id": "comp-widget",
            "criterion_id": "AC-WIDGET-002",
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_002.py",
                "content": test_content,
            },
            "model_call_error": None,
        }

    spec_before = snapshot(repo_root / "specs")
    gen_widget_before = snapshot(repo_root / "gen" / "widget")

    first = verifier_orchestrator.verify(
        "comp-widget", repo_root, judge=judge, test_author=test_author
    )

    judge_calls_1 = len(judge_log.read_text().splitlines()) if judge_log.exists() else 0
    author_calls_1 = len(author_log.read_text().splitlines()) if author_log.exists() else 0

    # Inputs remain unchanged between runs.
    assert snapshot(repo_root / "specs") == spec_before
    assert snapshot(repo_root / "gen" / "widget") == gen_widget_before

    second = verifier_orchestrator.verify(
        "comp-widget", repo_root, judge=judge, test_author=test_author
    )

    judge_calls_2 = len(judge_log.read_text().splitlines()) if judge_log.exists() else 0
    author_calls_2 = len(author_log.read_text().splitlines()) if author_log.exists() else 0

    # The judge was actually consulted, the same way on both runs.
    assert judge_calls_1 > 0
    assert judge_calls_2 == 2 * judge_calls_1
    assert author_calls_2 == 2 * author_calls_1

    d1 = report_dict(first)
    d2 = report_dict(second)

    assert d1 == d2
    assert json.dumps(d1, sort_keys=True, default=str) == json.dumps(
        d2, sort_keys=True, default=str
    )

    for name in (
        "component_id",
        "criteria",
        "requirement_results",
        "interface_drift",
        "mutation_score",
        "mutation_error",
        "overall",
    ):
        assert field(first, name) == field(second, name)

    ids_1 = [field(c, "id") for c in field(first, "criteria")]
    ids_2 = [field(c, "id") for c in field(second, "criteria")]
    assert ids_1 == ids_2
    assert set(ids_1) == {"AC-WIDGET-001", "AC-WIDGET-002"}