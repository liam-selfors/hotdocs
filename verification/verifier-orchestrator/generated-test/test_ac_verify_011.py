# hotdocs-criterion: sha256:04c4f9672d8633ccb1a4bccda5c0eb210d83a947107d9652ceb5fb49b592a0aa
import json
import re
from pathlib import Path

import verifier_orchestrator


CRITERIA = [
    # (criterion id, covers, kind, gherkin marker text)
    ("AC-WIDGET-001", "R-WIDGET-001", "generated-test",
     "Given a widget_alpha is 2\nWhen widget.double is invoked with [widget_alpha]\nThen result equals 4"),
    ("AC-WIDGET-002", "R-WIDGET-001", "generated-test",
     "Given a widget_beta is 3\nWhen widget.double is invoked with [widget_beta]\nThen result equals 6"),
    ("AC-WIDGET-003", "R-WIDGET-002", "generated-test",
     "Given a widget_gamma is 5\nWhen widget.triple is invoked with [widget_gamma]\nThen result equals 15"),
    ("AC-WIDGET-004", "R-WIDGET-003", "llm-judge",
     "Given a widget_delta is 1\nWhen widget.describe is invoked with [widget_delta]\nThen result equals \"clear\""),
]

REQUIREMENTS = {
    "R-WIDGET-001": "**R-WIDGET-001** — `double(x)` MUST return `2 * x`.",
    "R-WIDGET-002": "**R-WIDGET-002** — `triple(x)` MUST return `3 * x`.",
    "R-WIDGET-003": "**R-WIDGET-003** — `describe(x)` documentation MUST be clear.",
}

PASSING_TEST = "def test_widget_ok():\n    assert 2 * 2 == 4\n"
FAILING_TEST = (
    "def test_widget_bad():\n"
    "    expected_marker_value = 15\n"
    "    actual_marker_value = 14\n"
    "    assert actual_marker_value == expected_marker_value\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** — a test term.\n")

    write(
        repo_root / "specs" / "product" / "widgeting.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widgeting\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widgeting\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets get computed.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-WIDGET-001\n"
        "Covers: P-WIDGET\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a w is 1\n"
        "When widget.double is invoked with [w]\n"
        "Then result equals 2\n"
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
        "Widget computes multiples of a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: multiples.\n"
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
    for rid, text in REQUIREMENTS.items():
        write(comp / "requirements" / (rid + ".md"), "# " + rid + "\n\n" + text + "\n")
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble(x: int) -> int\ntriple(x: int) -> int\ndescribe(x: int) -> str\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    for cid, covers, kind, gherkin in CRITERIA:
        write(
            comp / "acceptance" / (cid + ".md"),
            "# " + cid + "\n"
            "\n"
            "Covers: " + covers + "\n"
            "Kind: " + kind + "\n"
            "\n"
            "```gherkin\n" + gherkin + "\n```\n",
        )

    # Component's real code: empty module, the generated tests import nothing.
    write(repo_root / "gen" / "widget" / "widget.py", "")

    # spec-bundle-assembler stand-in.
    covers_map = dict((c[0], c[1]) for c in CRITERIA)
    text_map = dict((c[0], c[3]) for c in CRITERIA)
    interface_text = (comp / "interface" / "library.md").read_text(encoding="utf-8")
    glossary_text = (repo_root / "specs" / "glossary.md").read_text(encoding="utf-8")
    assembler_src = (
        "COVERS = " + repr(covers_map) + "\n"
        "TEXTS = " + repr(text_map) + "\n"
        "REQS = " + repr(REQUIREMENTS) + "\n"
        "INTERFACE = " + repr(interface_text) + "\n"
        "GLOSSARY = " + repr(glossary_text) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    covers = COVERS[criterion_id]\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': covers,\n"
        "        'criterion_text': TEXTS[criterion_id],\n"
        "        'requirement_text': REQS[covers],\n"
        "        'interface': INTERFACE,\n"
        "        'glossary': GLOSSARY,\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler_src)


def make_test_author(log_path):
    def test_author_stub(bundle):
        cid = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(cid + "\n")
        content = FAILING_TEST if cid == "AC-WIDGET-003" else PASSING_TEST
        return {
            "component_id": "comp-widget",
            "criterion_id": cid,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_" + cid.lower().replace("-", "_") + ".py",
                "content": content,
            },
            "model_call_error": None,
        }

    return test_author_stub


def check_boolean_only(rr):
    assert isinstance(rr, dict)
    for key, value in rr.items():
        assert isinstance(key, str) and re.fullmatch(r"R-[A-Z0-9]+-\d+", key), key
        assert isinstance(value, str) and value in ("pass", "fail"), value
    dumped = json.dumps(rr)
    forbidden = ["Given", "When", "Then", "rationale", "expected", "actual", "widget_alpha",
                 "widget_gamma", "AC-WIDGET", "failure_detail", "message", "skipped"]
    for cid, _covers, _kind, gherkin in CRITERIA:
        for line in gherkin.splitlines():
            forbidden.append(line)
    for word in forbidden:
        assert word not in dumped, word


def test_requirement_results_projection_is_boolean_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author_calls.log"

    report = verifier_orchestrator.verify(
        "comp-widget", repo_root, judge=None, test_author=make_test_author(log_path)
    )

    # Sanity: the per-criterion results are what the scenario sets up.
    criteria = field(report, "criteria")
    by_id = dict((field(c, "id"), field(c, "result")) for c in criteria)
    assert by_id.get("AC-WIDGET-001") == "pass"
    assert by_id.get("AC-WIDGET-002") == "pass"
    assert by_id.get("AC-WIDGET-003") == "fail"
    assert by_id.get("AC-WIDGET-004") == "skipped"

    expected = {"R-WIDGET-001": "pass", "R-WIDGET-002": "fail", "R-WIDGET-003": "fail"}

    rr = field(report, "requirement_results")
    assert rr == expected
    check_boolean_only(rr)

    as_dict = report.to_dict()
    rr_json = as_dict["requirement_results"]
    assert rr_json == expected
    check_boolean_only(rr_json)