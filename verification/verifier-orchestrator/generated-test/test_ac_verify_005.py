# hotdocs-criterion: sha256:94cdf25638a0f73fa3db7c7842731f02b0e5efb7a9e03ae62817fb6a3477ac74
import hashlib
import json
import shutil
from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"

CRITERIA = {
    "AC-WIDGET-001": {"covers": "R-WIDGET-001", "kind": "compiled"},
    "AC-WIDGET-002": {"covers": "R-WIDGET-002", "kind": "generated-test"},
    "AC-WIDGET-003": {"covers": "R-WIDGET-003", "kind": "llm-judge"},
}

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "widget_echo(x) -> object\n"
    "```\n"
    "\n"
    "`widget_echo` returns an object whose `value` attribute is `x`.\n"
)

MODULE_SOURCE = (
    "class _Result:\n"
    "    def __init__(self, value):\n"
    "        self.value = value\n"
    "\n"
    "\n"
    "def widget_echo(x):\n"
    "    return _Result(x)\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def bundle_for(criterion_id):
    info = CRITERIA[criterion_id]
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": criterion_id,
        "covers": info["covers"],
        "criterion_text": "criterion text for " + criterion_id,
        "requirement_text": "requirement text for " + info["covers"],
        "interface": LIBRARY_MD,
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
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** — a thing.\n")
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
        "Echo widgets.\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
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
        "Echoes a value back.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: echoing.\n"
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
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n`widget_echo(x)` MUST return an object whose `value` is `x`.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-002.md",
        "# R-WIDGET-002\n\n`widget_echo(3).value` MUST be `3`.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-003.md",
        "# R-WIDGET-003\n\nThe interface text MUST be clear.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a n is 4\n"
        "When widget_echo is invoked with [n]\n"
        "Then value equals 4\n"
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
        "Given the widget module\n"
        "When widget_echo is called with 3\n"
        "Then its value is 3\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-003.md",
        "# AC-WIDGET-003\n"
        "\n"
        "Covers: R-WIDGET-003\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the widget interface text\n"
        "When a reader reads it\n"
        "Then it is clear\n"
        "```\n",
    )

    write(repo_root / "gen" / SLUG / "widget.py", MODULE_SOURCE)

    bundles = {cid: bundle_for(cid) for cid in CRITERIA}
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLES = " + repr(bundles) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLES[criterion_id])\n",
    )

    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
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
        "    return ProbeReport()\n",
    )

    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1] / "spec-bundle-assembler"
    ).resolve().parents[1]
    shutil.copytree(
        live / "pipeline" / "criterion-compiler",
        repo_root / "pipeline" / "criterion-compiler",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    return bundles


def make_test_author(bundles, log_path):
    def test_author_stand_in(bundle):
        criterion_id = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(criterion_id) + "\n")
        content = (
            header_for(bundles[criterion_id]) + "\n"
            "import widget\n"
            "\n"
            "\n"
            "def test_echo_value():\n"
            "    assert widget.widget_echo(3).value == 3\n"
        )
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_002.py",
                "content": content,
            },
        }

    return test_author_stand_in


def test_skipped_llm_judge_alone_does_not_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bundles = build_fixture(repo_root)
    log_path = tmp_path / "author_calls.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID,
        repo_root,
        judge=None,
        test_author=make_test_author(bundles, log_path),
    )

    criteria = field(report, "criteria")
    by_id = {field(c, "id"): c for c in criteria}

    # The Given: every compiled and generated-test criterion passes,
    # mutation_score is 1.0, no drift, and the llm-judge criterion is skipped.
    assert field(by_id["AC-WIDGET-001"], "result") == "pass", by_id["AC-WIDGET-001"]
    assert field(by_id["AC-WIDGET-002"], "result") == "pass", by_id["AC-WIDGET-002"]
    assert field(by_id["AC-WIDGET-003"], "result") == "skipped", by_id["AC-WIDGET-003"]
    assert field(report, "mutation_score") == 1.0
    assert field(report, "interface_drift") is False

    # The Then: a skipped finding alone never causes fail.
    assert field(report, "overall") == "pass"
    assert report.to_dict()["overall"] == "pass"