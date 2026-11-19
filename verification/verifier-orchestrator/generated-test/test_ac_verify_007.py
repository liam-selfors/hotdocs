# hotdocs-criterion: sha256:ca4c4e91c0dc7bef09feb5cf84ecedac5f6146725e96f39845dfe8563d4a96dc
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERION_TEXTS = {
    "AC-WIDGET-001": (
        "Given a number 2\n"
        "When double is called with it\n"
        "Then it returns 4\n"
    ),
    "AC-WIDGET-002": (
        "Given the widget spec\n"
        "When a reviewer reads it\n"
        "Then it is clear\n"
    ),
}

REQUIREMENT_TEXTS = {
    "R-WIDGET-001": "**R-WIDGET-001** — `double(x)` MUST return `2 * x`.",
    "R-WIDGET-002": "**R-WIDGET-002** — The widget spec MUST be clear.",
}

COVERS = {"AC-WIDGET-001": "R-WIDGET-001", "AC-WIDGET-002": "R-WIDGET-002"}


def build_fixture(repo_root, log_path):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** — a test term.\n")
    write(
        repo_root / "specs" / "product" / "widgeting.md",
        "---\n"
        "id: P-WIDGETING\n"
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
        "- In scope: doubling.\n",
    )
    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGETING]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget doubles a number.\n",
    )
    write(comp / "requirements" / "R-WIDGET-001.md", "# R-WIDGET-001\n\n" + REQUIREMENT_TEXTS["R-WIDGET-001"] + "\n")
    write(comp / "requirements" / "R-WIDGET-002.md", "# R-WIDGET-002\n\n" + REQUIREMENT_TEXTS["R-WIDGET-002"] + "\n")
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n\nCovers: R-WIDGET-001\nKind: generated-test\n\n```gherkin\n"
        + CRITERION_TEXTS["AC-WIDGET-001"]
        + "```\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-002.md",
        "# AC-WIDGET-002\n\nCovers: R-WIDGET-002\nKind: llm-judge\n\n```gherkin\n"
        + CRITERION_TEXTS["AC-WIDGET-002"]
        + "```\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n```\ndouble(x: int) -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(repo_root / "gen" / "widget" / "widget.py", "def double(x):\n    return x * 2\n")

    assembler_src = (
        "from pathlib import Path\n"
        "\n"
        "CRITERION_TEXTS = " + repr(CRITERION_TEXTS) + "\n"
        "REQUIREMENT_TEXTS = " + repr(REQUIREMENT_TEXTS) + "\n"
        "COVERS = " + repr(COVERS) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('assemble_criterion ' + criterion_id + '\\n')\n"
        "    covers = COVERS[criterion_id]\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': covers,\n"
        "        'criterion_text': CRITERION_TEXTS[criterion_id],\n"
        "        'requirement_text': REQUIREMENT_TEXTS[covers],\n"
        "        'interface': '# Library\\n\\ndouble(x: int) -> int',\n"
        "        'glossary': '# Glossary',\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler_src)

    compiler_src = (
        "from dataclasses import dataclass, field\n"
        "\n"
        "GATE_VERSION = 'criterion-compiler@1.0.0'\n"
        "\n"
        "@dataclass\n"
        "class InterfaceSurface:\n"
        "    functions: dict = field(default_factory=dict)\n"
        "    types: dict = field(default_factory=dict)\n"
        "    module_name: str = ''\n"
        "\n"
        "@dataclass\n"
        "class ParsedCriterion:\n"
        "    criterion_id: str\n"
        "    covers: str\n"
        "    kind: str\n"
        "    gherkin: str\n"
        "    file: str\n"
        "\n"
        "@dataclass\n"
        "class CompileReport:\n"
        "    outputs: list\n"
        "    gate_version: str\n"
        "    summary: dict\n"
        "\n"
        "def compile(component_id, repo_root, target='pytest', out_dir=None):\n"
        "    return CompileReport(outputs=[], gate_version=GATE_VERSION,\n"
        "                         summary={'compiled': 0, 'errors': 0, 'skipped_non_compiled_kind': 2})\n"
        "\n"
        "def compile_criterion(criterion, surface=None):\n"
        "    return {'status': 'error', 'message': 'line 1: not supported in stand-in'}\n"
    )
    write(repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py", compiler_src)


TEST_CONTENT = (
    "import widget\n"
    "\n"
    "\n"
    "def test_double():\n"
    "    assert widget.double(2) == 4\n"
    "    assert widget.double(3) == 6\n"
)


def make_test_author(log_path):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("test_author\n")
        return {
            "component_id": "comp-widget",
            "criterion_id": "AC-WIDGET-001",
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": TEST_CONTENT,
            },
            "model_call_error": None,
        }

    return test_author


def test_verify_produces_exactly_one_verification_report(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    build_fixture(repo_root, log_path)

    report = verifier_orchestrator.verify(
        "comp-widget", repo_root, test_author=make_test_author(log_path)
    )

    # Exactly one report: a single dataclass instance, not a collection or bare dict.
    assert report is not None
    assert not isinstance(report, (list, tuple, set, dict))
    assert type(report).__name__ == "VerificationReport"

    assert field(report, "component_id") == "comp-widget"

    criteria = field(report, "criteria")
    assert isinstance(criteria, list)
    ids = [c["id"] for c in criteria]
    assert sorted(ids) == ["AC-WIDGET-001", "AC-WIDGET-002"]
    assert len(ids) == len(set(ids))
    for c in criteria:
        assert isinstance(c, dict)
        assert c["result"] in ("pass", "fail", "skipped")
        assert c["covers"] == COVERS[c["id"]]
    by_id = {c["id"]: c for c in criteria}
    assert by_id["AC-WIDGET-001"]["kind"] == "generated-test"
    assert by_id["AC-WIDGET-001"]["result"] == "pass"
    assert by_id["AC-WIDGET-002"]["kind"] == "llm-judge"
    assert by_id["AC-WIDGET-002"]["result"] == "skipped"

    mutation_score = field(report, "mutation_score")
    assert mutation_score is None or isinstance(mutation_score, (int, float))
    assert not isinstance(mutation_score, bool)

    interface_drift = field(report, "interface_drift")
    assert isinstance(interface_drift, bool)

    overall = field(report, "overall")
    assert overall in ("pass", "fail")

    # The JSON form carries the same single report with all required keys.
    as_dict = report.to_dict()
    assert isinstance(as_dict, dict)
    for key in ("component_id", "criteria", "mutation_score", "interface_drift", "overall"):
        assert key in as_dict
    assert as_dict["overall"] == overall
    assert as_dict["interface_drift"] == interface_drift
    assert as_dict["mutation_score"] == mutation_score
    assert sorted(c["id"] for c in as_dict["criteria"]) == ["AC-WIDGET-001", "AC-WIDGET-002"]
    json.dumps(as_dict)

    # The test_author stand-in ran once for the one generated-test criterion.
    calls = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line == "test_author"]
    assert len(calls) == 1