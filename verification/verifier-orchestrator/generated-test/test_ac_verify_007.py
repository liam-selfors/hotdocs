# hotdocs-criterion: sha256:d0236924d9868d2706bca47f2014627428ba238878f42ebfbbe3895d1699643d
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERIA = {
    "AC-WIDGET-001": ("R-WIDGET-001", "generated-test"),
    "AC-WIDGET-002": ("R-WIDGET-002", "llm-judge"),
}


GENERATED_TEST_SOURCE = (
    "import widget\n"
    "\n"
    "\n"
    "def test_value_is_three():\n"
    "    assert widget.VALUE == 3\n"
)


def build_fixture(repo_root):
    repo_root = Path(repo_root)

    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** - a thing under test.\n",
    )
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
        "Provide a widget value.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the widget value.\n",
    )

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
        "Exposes a constant widget value.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: the value.\n"
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
        "**R-WIDGET-001** - The module MUST expose `VALUE` equal to 3.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-002.md",
        "**R-WIDGET-002** - The spec MUST be clear.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nVALUE: int  # 3\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the widget module\n"
        "When VALUE is read\n"
        "Then it equals 3\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-002.md",
        "# AC-WIDGET-002\n"
        "\n"
        "Covers: R-WIDGET-002\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the widget spec\n"
        "When a reviewer reads it\n"
        "Then it is clear\n"
        "```\n",
    )

    # Component code: no mutation sites (a numeric constant is never a site).
    write(repo_root / "gen" / "widget" / "widget.py", "VALUE = 3\n")

    # spec-bundle-assembler stand-in.
    covers_map = {cid: cov for cid, (cov, _kind) in CRITERIA.items()}
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "COVERS = " + repr(covers_map) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': COVERS.get(criterion_id, ''),\n"
        "        'criterion_text': 'criterion ' + criterion_id,\n"
        "        'requirement_text': 'requirement for ' + criterion_id,\n"
        "        'interface': 'VALUE: int',\n"
        "        'glossary': 'glossary',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n",
    )

    # test-probe stand-in: always ok, no findings.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )
    return repo_root


def make_author(log_path):
    def author_stub(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(field(bundle, "criterion_id")) + "\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": GENERATED_TEST_SOURCE,
            },
        }

    return author_stub


def make_judge(log_path):
    def judge_stub(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(field(bundle, "criterion_id")) + "\n")
        return {"result": "pass", "rationale": "clear enough"}

    return judge_stub


def test_verify_produces_exactly_one_structured_report(tmp_path):
    repo_root = build_fixture(tmp_path / "repo")
    author_log = tmp_path / "author.log"
    judge_log = tmp_path / "judge.log"

    report = verifier_orchestrator.verify(
        "comp-widget",
        repo_root,
        judge=make_judge(judge_log),
        test_author=make_author(author_log),
    )

    # Exactly one report object, not a collection of reports.
    assert report is not None
    assert not isinstance(report, (list, tuple, set))
    assert hasattr(report, "to_dict")

    as_dict = report.to_dict()
    assert isinstance(as_dict, dict)
    # The JSON form is one serializable document.
    reparsed = json.loads(json.dumps(as_dict))
    assert isinstance(reparsed, dict)

    for key in ("component_id", "criteria", "mutation_score", "interface_drift", "overall", "assets"):
        assert key in as_dict, key

    assert field(report, "component_id") == "comp-widget"
    assert as_dict["component_id"] == "comp-widget"

    # Per-criterion results: one entry per acceptance criterion.
    criteria = field(report, "criteria")
    assert isinstance(criteria, list)
    ids = [field(c, "id") for c in criteria]
    assert sorted(ids) == sorted(CRITERIA.keys())
    assert len(ids) == len(set(ids))
    for c in criteria:
        cid = field(c, "id")
        assert field(c, "result") in ("pass", "fail", "skipped")
        assert field(c, "covers") == CRITERIA[cid][0]
        assert field(c, "kind") == CRITERIA[cid][1]

    dict_ids = sorted(c["id"] for c in as_dict["criteria"])
    assert dict_ids == sorted(CRITERIA.keys())

    # Mutation score: a number in [0, 1] or null.
    score = field(report, "mutation_score")
    assert score is None or (
        isinstance(score, (int, float)) and not isinstance(score, bool) and 0.0 <= score <= 1.0
    )
    assert as_dict["mutation_score"] == score

    # Interface drift: a boolean.
    drift = field(report, "interface_drift")
    assert isinstance(drift, bool)
    assert as_dict["interface_drift"] == drift

    # Overall verdict.
    overall = field(report, "overall")
    assert overall in ("pass", "fail")
    assert as_dict["overall"] == overall

    # Declared assets: the implicit python asset first.
    assets = field(report, "assets")
    assert isinstance(assets, list)
    assert len(assets) >= 1
    assert field(assets[0], "kind") == "python"
    assert field(assets[0], "path") == "."