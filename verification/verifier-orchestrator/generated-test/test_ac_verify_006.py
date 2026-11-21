# hotdocs-criterion: sha256:b3540c1b261c8547479642959b54ef586b06c481c30f4a315e0b30f357dfb90e
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"

BUNDLE = {
    "component_id": COMPONENT_ID,
    "criterion_id": CRITERION_ID,
    "covers": REQUIREMENT_ID,
    "criterion_text": "Given a widget\nWhen add is invoked with [2, 3]\nThen result equals 5",
    "requirement_text": "R-WIDGET-001: add MUST return the sum of its two arguments.",
    "interface": "add(a, b) -> int\nis_big(x) -> bool\nis_small(x) -> bool\nenabled() -> bool",
    "glossary": "Widget glossary.",
    "dependency_interfaces": {},
    "testing": "",
}

# Four mutation sites (python adapter's strength check): `+`, `>`, `<`, `True`.
# The authored test only kills the `+` mutant, so the score is 1/4 = 0.25.
WIDGET_SOURCE = (
    "def add(a, b):\n"
    "    return a + b\n"
    "\n"
    "\n"
    "def is_big(x):\n"
    "    return x > 10\n"
    "\n"
    "\n"
    "def is_small(x):\n"
    "    return x < 3\n"
    "\n"
    "\n"
    "def enabled():\n"
    "    return True\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def criterion_header():
    payload = json.dumps(
        {k: BUNDLE[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n\nAdds numbers.\n\n"
        "## Scope\n\n- In scope: adding.\n\n"
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
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n\n**" + REQUIREMENT_ID + "** — `add` MUST return the sum of its two arguments.\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When add is invoked with [2, 3]\n"
        "Then result equals 5\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nadd(a, b) -> int\nis_big(x) -> bool\nis_small(x) -> bool\nenabled() -> bool\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Widget capability\n\n## Purpose\n\nWidgets.\n",
    )

    # The component's own code.
    write(repo_root / "gen" / SLUG / "widget.py", WIDGET_SOURCE)

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )


def weak_test_source():
    return (
        criterion_header() + "\n"
        "import widget\n"
        "\n"
        "\n"
        "def test_add():\n"
        "    assert widget.add(2, 3) == 5\n"
    )


def make_test_author(log_path):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": weak_test_source(),
            },
        }

    return author


def test_mutation_score_below_bar_fails_overall(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=None, test_author=make_test_author(log_path)
    )

    # The fake test author actually supplied the test.
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").count("called") >= 1

    criteria = field(report, "criteria")
    entries = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(entries) == 1
    entry = entries[0]
    assert field(entry, "kind") == "generated-test"
    # The test passes on the unmutated code; the mutation score changes only
    # the overall verdict, never the criterion's own result.
    assert field(entry, "result") == "pass"

    # The shortfall is reported: a real score, below the 0.8 bar, no error.
    score = field(report, "mutation_score")
    assert score is not None
    assert score < 0.8
    assert abs(score - 0.25) < 1e-9
    assert field(report, "mutation_error") is None

    assert field(report, "overall") == "fail"

    as_dict = report.to_dict()
    assert as_dict["overall"] == "fail"
    assert as_dict["mutation_score"] is not None
    assert as_dict["mutation_score"] < 0.8
    assert as_dict["mutation_error"] is None