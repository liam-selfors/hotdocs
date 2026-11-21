# hotdocs-criterion: sha256:d044b885bec597b5f73cde264cec274a6a127d16cbe9b12c524381eaadd00698
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"

INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "double(x: int) -> int\n"
    "```\n"
)

REQ_1 = "**R-WIDGET-001** — The widget spec MUST be clear."
REQ_2 = "**R-WIDGET-002** — `double(x)` MUST return twice `x`."

CRIT_1 = (
    "Given the widget spec\n"
    "When a reviewer reads it\n"
    "Then it is clear"
)
CRIT_2 = (
    "Given an integer 2\n"
    "When double is called with it\n"
    "Then the result is 4"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def bundle_for(criterion_id, covers, criterion_text, requirement_text):
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": criterion_id,
        "covers": covers,
        "criterion_text": criterion_text,
        "requirement_text": requirement_text,
        "interface": INTERFACE_TEXT,
        "glossary": "",
        "dependency_interfaces": {},
        "testing": "",
    }


def header_for(bundle):
    keys = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    payload = json.dumps(
        {k: bundle[k] for k in keys},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / SLUG

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
        "Doubles numbers.\n",
    )

    write(
        comp_dir / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
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
        "Doubles numbers.\n"
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
    write(comp_dir / "requirements" / "R-WIDGET-001.md", "# R-WIDGET-001\n\n" + REQ_1 + "\n")
    write(comp_dir / "requirements" / "R-WIDGET-002.md", "# R-WIDGET-002\n\n" + REQ_2 + "\n")
    write(comp_dir / "interface" / "library.md", INTERFACE_TEXT)
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp_dir / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n" + CRIT_1 + "\n```\n",
    )
    write(
        comp_dir / "acceptance" / "AC-WIDGET-002.md",
        "# AC-WIDGET-002\n"
        "\n"
        "Covers: R-WIDGET-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n" + CRIT_2 + "\n```\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    # Code under test.
    write(
        repo_root / "gen" / SLUG / "widget.py",
        "def double(x):\n"
        "    return x * 2\n",
    )

    bundles = {
        "AC-WIDGET-001": bundle_for("AC-WIDGET-001", "R-WIDGET-001", CRIT_1, REQ_1),
        "AC-WIDGET-002": bundle_for("AC-WIDGET-002", "R-WIDGET-002", CRIT_2, REQ_2),
    }

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLES = " + repr(bundles) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLES[criterion_id])\n",
    )

    # test-probe stand-in: always ok.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self, ok, findings, tests_run, tests_reached):\n"
        "        self.ok = ok\n"
        "        self.findings = findings\n"
        "        self.tests_run = tests_run\n"
        "        self.tests_reached = tests_reached\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport(True, [], 1, 1)\n",
    )

    generated_test = (
        header_for(bundles["AC-WIDGET-002"]) + "\n"
        "import widget\n"
        "\n"
        "\n"
        "def test_double():\n"
        "    assert widget.double(2) == 4\n"
        "    assert widget.double(3) == 6\n"
    )
    return generated_test


def make_judge(log_path):
    def judge(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("judge\n")
        return {"result": "pass", "rationale": "The spec is clear."}

    return judge


def make_test_author(log_path, content):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("author\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": "AC-WIDGET-002",
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_002.py",
                "content": content,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author


def test_verify_twice_yields_identical_reports(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    generated_test = build_fixture(repo_root)

    judge_log = tmp_path / "judge.log"
    author_log = tmp_path / "author.log"
    judge = make_judge(judge_log)
    test_author = make_test_author(author_log, generated_test)

    report1 = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=judge, test_author=test_author
    )
    report2 = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=judge, test_author=test_author
    )

    # Non-vacuity: both criteria were evaluated and the judge was consulted.
    criteria1 = field(report1, "criteria")
    assert len(criteria1) == 2
    assert judge_log.is_file()
    assert len(judge_log.read_text(encoding="utf-8").splitlines()) >= 2

    d1 = report1.to_dict()
    d2 = report2.to_dict()
    assert json.dumps(d1, sort_keys=True, default=str) == json.dumps(
        d2, sort_keys=True, default=str
    )
    assert d1 == d2
    assert report1 == report2