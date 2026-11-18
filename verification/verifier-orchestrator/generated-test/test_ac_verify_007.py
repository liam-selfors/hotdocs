# hotdocs-criterion: sha256:ca4c4e91c0dc7bef09feb5cf84ecedac5f6146725e96f39845dfe8563d4a96dc
import dataclasses
import json
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"

GEN_CRITERION_ID = "AC-WIDGET-001"
JUDGE_CRITERION_ID = "AC-WIDGET-002"

GLOSSARY_TEXT = "# Glossary\n\n- **Widget** \u2014 a test term.\n"

INTERFACE_TEXT = "# Library\n\n```\ndouble(x: int) -> int\n```\n"

REQ1_TEXT = "# R-WIDGET-001\n\n**R-WIDGET-001** \u2014 `double(x)` MUST return `2 * x`.\n"
REQ2_TEXT = "# R-WIDGET-002\n\n**R-WIDGET-002** \u2014 The interface MUST be described clearly.\n"

AC1_TEXT = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When double(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

AC2_TEXT = (
    "# AC-WIDGET-002\n"
    "\n"
    "Covers: R-WIDGET-002\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given the widget interface\n"
    "When a reviewer reads it\n"
    "Then it is clear\n"
    "```\n"
)

GENERATED_TEST_CONTENT = (
    "import widget\n"
    "\n"
    "\n"
    "def test_double():\n"
    "    assert widget.double(2) == 4\n"
    "    assert widget.double(3) == 6\n"
    "    assert widget.double(0) == 0\n"
)

VALID_RESULTS = {"pass", "fail", "skipped"}
EXPECTED_KEYS = {"component_id", "criteria", "mutation_score", "interface_drift", "overall"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(root):
    write(root / "specs" / "glossary.md", GLOSSARY_TEXT)
    write(
        root / "specs" / "product" / "widgets.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widgets\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widgets\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets double numbers.\n",
    )
    comp = root / "specs" / "components" / SLUG
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
    write(comp / "requirements" / "R-WIDGET-001.md", REQ1_TEXT)
    write(comp / "requirements" / "R-WIDGET-002.md", REQ2_TEXT)
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(comp / "acceptance" / "AC-WIDGET-001.md", AC1_TEXT)
    write(comp / "acceptance" / "AC-WIDGET-002.md", AC2_TEXT)

    write(
        root / "gen" / SLUG / "widget.py",
        "def double(x):\n"
        "    return 2 * x\n",
    )

    log_path = root.parent / (root.name + "-assembler-calls.log")
    criteria = {
        GEN_CRITERION_ID: {
            "covers": "R-WIDGET-001",
            "criterion_text": AC1_TEXT,
            "requirement_text": REQ1_TEXT,
        },
        JUDGE_CRITERION_ID: {
            "covers": "R-WIDGET-002",
            "criterion_text": AC2_TEXT,
            "requirement_text": REQ2_TEXT,
        },
    }
    assembler_source = (
        "CRITERIA = " + repr(criteria) + "\n"
        "INTERFACE = " + repr(INTERFACE_TEXT) + "\n"
        "GLOSSARY = " + repr(GLOSSARY_TEXT) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(criterion_id) + '\\n')\n"
        "    info = CRITERIA.get(criterion_id, {'covers': '', 'criterion_text': '', 'requirement_text': ''})\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': info['covers'],\n"
        "        'criterion_text': info['criterion_text'],\n"
        "        'requirement_text': info['requirement_text'],\n"
        "        'interface': INTERFACE,\n"
        "        'glossary': GLOSSARY,\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler_source)
    return root


def make_test_author(log_path):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(field(bundle, "criterion_id")) + "\n")
        return {
            "component_id": field(bundle, "component_id"),
            "criterion_id": field(bundle, "criterion_id"),
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": GENERATED_TEST_CONTENT,
            },
            "model_call_error": None,
        }

    return test_author


def check_report_dict(data):
    assert isinstance(data, dict)
    for key in EXPECTED_KEYS:
        assert key in data, "missing key " + key
    assert data["component_id"] == COMPONENT_ID

    criteria = data["criteria"]
    assert isinstance(criteria, list)
    ids = [c["id"] for c in criteria]
    assert sorted(ids) == sorted([GEN_CRITERION_ID, JUDGE_CRITERION_ID])
    for c in criteria:
        assert isinstance(c, dict)
        assert c["result"] in VALID_RESULTS

    by_id = {c["id"]: c for c in criteria}
    assert by_id[JUDGE_CRITERION_ID]["result"] == "skipped"

    score = data["mutation_score"]
    assert score is None or (
        isinstance(score, (int, float)) and not isinstance(score, bool) and 0.0 <= score <= 1.0
    )
    assert isinstance(data["interface_drift"], bool)
    assert data["overall"] in {"pass", "fail"}


def test_verify_produces_exactly_one_report(tmp_path):
    root = build_fixture(tmp_path / "repo")
    author_log = tmp_path / "author-calls.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID, root, test_author=make_test_author(author_log)
    )

    # Exactly one report: a single dataclass instance, not a list or bare dict.
    assert not isinstance(report, (list, tuple, set, dict))
    assert dataclasses.is_dataclass(report) and not isinstance(report, type)

    # Attribute access on the report itself.
    assert report.component_id == COMPONENT_ID
    assert isinstance(report.criteria, list)
    for c in report.criteria:
        assert isinstance(c, dict)
    assert report.overall in {"pass", "fail"}
    assert isinstance(report.interface_drift, bool)
    score = report.mutation_score
    assert score is None or 0.0 <= score <= 1.0

    # JSON form carries per-criterion results, mutation_score, interface_drift, overall.
    data = report.to_dict()
    check_report_dict(data)
    json.dumps(data)

    assert data["overall"] == report.overall
    assert data["interface_drift"] == report.interface_drift
    assert data["mutation_score"] == report.mutation_score
    assert [c["id"] for c in data["criteria"]] == [c["id"] for c in report.criteria]


def test_cli_json_prints_exactly_one_report(tmp_path, capsys):
    root = build_fixture(tmp_path / "repo")

    code = verifier_orchestrator.main(
        [COMPONENT_ID, "--repo-root=" + str(root), "--format=json"]
    )
    out = capsys.readouterr().out

    # The whole stdout parses as one single JSON object: exactly one report.
    data = json.loads(out.strip())
    check_report_dict(data)

    assert code in (0, 1)
    assert code == (0 if data["overall"] == "pass" else 1)