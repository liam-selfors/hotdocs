# hotdocs-criterion: sha256:d95642b64fbb56eba460117c0d719f3e222a501cd7c09af3b3a0c0d5d8fe1a8f
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BUNDLE = {
    "component_id": "comp-widget",
    "criterion_id": "AC-WIDGET-001",
    "covers": "R-WIDGET-001",
    "criterion_text": "Given two numbers When g is called Then it orders them",
    "requirement_text": "R-WIDGET-001: g MUST report whether a is less than b.",
    "interface": "g(a, b) -> bool\nh(a, b) -> int\nm(k, d) -> bool\ndo_the_thing(x) -> object",
    "glossary": "Glossary text.",
    "dependency_interfaces": {},
    "testing": "",
}

MODULE_SOURCE = (
    "def g(a, b):\n"
    "    return a < b\n"
    "\n"
    "\n"
    "def h(a, b):\n"
    "    return a // b\n"
    "\n"
    "\n"
    "def m(k, d):\n"
    "    return k in d\n"
    "\n"
    "\n"
    "def do_the_thing(x):\n"
    "    return x\n"
)

TEST_BODY = (
    "import widget\n"
    "\n"
    "\n"
    "def test_g_orders_numbers():\n"
    "    assert widget.g(1, 2) is True\n"
    "    assert widget.g(2, 1) is False\n"
)


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
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
        "## Purpose\n\nCompares and divides numbers.\n\n"
        "## Scope\n\n- In scope: g, h, m, do_the_thing.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** - g MUST report whether a is less than b.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ng(a, b) -> bool\nh(a, b) -> int\nm(k, d) -> bool\ndo_the_thing(x) -> object\n```\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given two numbers\n"
        "When g is called\n"
        "Then it orders them\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Widget capability\n\n## Purpose\n\nWidgets.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    write(repo_root / "gen" / "widget" / "widget.py", MODULE_SOURCE)

    cached = header_for(BUNDLE) + "\n" + TEST_BODY
    write(
        repo_root / "verification" / "widget" / "generated-test" / "test_ac_widget_001.py",
        cached,
    )

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
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
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )
    return cached


def test_mutation_score_is_one_third(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cached = build_fixture(repo_root)
    log = tmp_path / "author.log"

    def test_author(bundle):
        with open(log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "ignored.py", "content": cached},
        }

    report = verifier_orchestrator.verify("comp-widget", repo_root, test_author=test_author)

    criteria = field(report, "criteria")
    entry = next(c for c in criteria if field(c, "id") == "AC-WIDGET-001")
    assert field(entry, "result") == "pass"
    assert field(report, "mutation_error") is None

    score = field(report, "mutation_score")
    assert score is not None
    assert abs(score - 1 / 3) < 1e-9