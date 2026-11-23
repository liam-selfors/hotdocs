# hotdocs-criterion: sha256:339ae6560d97f572556c65a37923a62f5f176d963e33d016a9602de848f574ca
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_MD = (
    "---\n"
    "id: comp-widget\n"
    "title: Widget\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "realizes: [P-WIDGET]\n"
    "---\n"
    "\n"
    "# Widget\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Computes a value for a widget.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: computing.\n"
    "- Out of scope: everything else.\n"
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
    "- Initial draft.\n"
)

PRODUCT_MD = (
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
    "Widgets compute values.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- Computing.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "compute(x: int) -> int\n"
    "```\n"
    "\n"
    "`compute` returns `x` unchanged.\n"
)

R1 = "# R-WIDGET-001\n\n**R-WIDGET-001** - `compute(x)` MUST return `x` unchanged.\n"
R2 = "# R-WIDGET-002\n\n**R-WIDGET-002** - The interface text MUST be clear.\n"

AC1 = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given an integer 2\n"
    "When compute is called with it\n"
    "Then the result is 2\n"
    "```\n"
)

AC2 = (
    "# AC-WIDGET-002\n"
    "\n"
    "Covers: R-WIDGET-002\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given the interface text\n"
    "When a reader reads it\n"
    "Then it is clear\n"
    "```\n"
)

ASSEMBLER_SRC = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': criterion_id.replace('AC-', 'R-'),\n"
    "        'criterion_text': 'criterion ' + criterion_id,\n"
    "        'requirement_text': 'requirement ' + criterion_id,\n"
    "        'interface': 'compute(x: int) -> int',\n"
    "        'glossary': 'glossary',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
    "\n"
    "\n"
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    raise RuntimeError('assemble is not expected to be called')\n"
)

PROBE_SRC = (
    "GATE_VERSION = 'test-probe@1.4.0'\n"
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
    "        return {'ok': self.ok, 'findings': list(self.findings),\n"
    "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
    "          interpreter=None, assets=None):\n"
    "    return ProbeReport()\n"
)

GENERATED_TEST = (
    "import widget\n"
    "\n"
    "\n"
    "def test_compute_returns_input():\n"
    "    assert widget.compute(2) == 2\n"
)


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "widget"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-WIDGET-001.md", R1)
    write(comp / "requirements" / "R-WIDGET-002.md", R2)
    write(comp / "acceptance" / "AC-WIDGET-001.md", AC1)
    write(comp / "acceptance" / "AC-WIDGET-002.md", AC2)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "specs" / "product" / "widget.md", PRODUCT_MD)
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** - a thing.\n")
    write(repo_root / "gen" / "widget" / "widget.py", "def compute(x):\n    return x\n")
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_SRC,
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SRC)


def make_test_author(log_path):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("author\n")
        criterion_id = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
        name = "test_" + criterion_id.lower().replace("-", "_") + ".py"
        return {
            "component_id": "comp-widget",
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/" + name,
                "content": GENERATED_TEST,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return author


def make_judge(log_path):
    def judge(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("judge\n")
        return {"result": "pass", "rationale": "clear enough"}

    return judge


def test_verify_produces_exactly_one_structured_report(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "calls.log"

    report = verifier_orchestrator.verify(
        "comp-widget",
        repo_root,
        judge=make_judge(log_path),
        test_author=make_test_author(log_path),
    )

    # Exactly one report: a single object, not a collection of reports.
    assert report is not None
    assert not isinstance(report, (list, tuple, set))
    assert hasattr(report, "to_dict")

    as_dict = report.to_dict()
    assert isinstance(as_dict, dict)
    json.dumps(as_dict)  # JSON form is serializable
    for key in ("criteria", "mutation_score", "interface_drift", "overall"):
        assert key in as_dict, key

    assert field(report, "component_id") == "comp-widget"

    # Per-criterion results: one entry per criterion, each exactly once.
    criteria = field(report, "criteria")
    assert isinstance(criteria, list)
    ids = [field(c, "id") for c in criteria]
    assert sorted(ids) == ["AC-WIDGET-001", "AC-WIDGET-002"]
    for c in criteria:
        assert field(c, "result") in ("pass", "fail", "skipped")

    # Mutation score.
    score = field(report, "mutation_score")
    assert score is None or (
        isinstance(score, (int, float)) and not isinstance(score, bool) and 0.0 <= score <= 1.0
    )

    # Interface drift.
    assert isinstance(field(report, "interface_drift"), bool)

    # Overall verdict.
    assert field(report, "overall") in ("pass", "fail")

    # Attribute and JSON forms agree.
    assert as_dict["overall"] == field(report, "overall")
    assert as_dict["interface_drift"] == field(report, "interface_drift")
    assert as_dict["mutation_score"] == field(report, "mutation_score")
    assert sorted(field(c, "id") for c in as_dict["criteria"]) == sorted(ids)