# hotdocs-criterion: sha256:1d680ab1feea19dd52bccdd180d5b74778649460c2dcdd3ea3115de5d3d97004
import importlib.util
import sys
from pathlib import Path

import verifier_orchestrator


SLUG = "weak-thing"
MODULE = "weak_thing"
COMPONENT_ID = "comp-weak-thing"
CRITERION_ID = "AC-WEAK-THING-001"
REQUIREMENT_ID = "R-WEAK-THING-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


MODULE_SOURCE = (
    "def double(x):\n"
    "    return x * 2\n"
    "\n"
    "\n"
    "def flag():\n"
    "    return True\n"
    "\n"
    "\n"
    "def compare(a, b):\n"
    "    return a == b\n"
)

WEAK_TEST_SOURCE = (
    "import weak_thing\n"
    "\n"
    "\n"
    "def test_double():\n"
    "    assert weak_thing.double(2) == 4\n"
)

STRONG_TEST_SOURCE = (
    "import weak_thing\n"
    "\n"
    "\n"
    "def test_double():\n"
    "    assert weak_thing.double(2) == 4\n"
    "\n"
    "\n"
    "def test_flag():\n"
    "    assert weak_thing.flag() is True\n"
    "\n"
    "\n"
    "def test_compare():\n"
    "    assert weak_thing.compare(1, 1) is True\n"
    "    assert weak_thing.compare(1, 2) is False\n"
)

ASSEMBLER_SOURCE = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
    "        'criterion_text': 'Given a number is 2 When double is invoked with [2] Then result equals 4',\n"
    "        'requirement_text': 'R-WEAK-THING-001 double MUST return twice its argument.',\n"
    "        'interface': 'double(x)\\nflag()\\ncompare(a, b)',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
)

PROBE_SOURCE = (
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
    "GATE_VERSION = 'test-probe@1.4.0'\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
    "          interpreter=None, assets=None):\n"
    "    return ProbeReport(True, [], 1, 1)\n"
)


def build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / SLUG
    write(
        comp_dir / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Weak thing\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: [P-WEAK]\n"
        "---\n"
        "\n"
        "# Weak thing\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubles numbers, returns a flag and compares values.\n"
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
        comp_dir / "requirements" / (REQUIREMENT_ID + ".md"),
        "**" + REQUIREMENT_ID + "** - `double` MUST return twice its argument.\n",
    )
    write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "double(x)\n"
        "flag()\n"
        "compare(a, b)\n"
        "```\n",
    )
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp_dir / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a number is 2\n"
        "When double is invoked with [2]\n"
        "Then result equals 4\n"
        "```\n",
    )
    write(
        repo_root / "specs" / "product" / "weak.md",
        "---\n"
        "id: P-WEAK\n"
        "title: Weak capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Weak capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubling.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), MODULE_SOURCE)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_SOURCE,
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)


def make_author(test_source, log_path):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/" + SLUG + "/generated-test/test_ac_weak_thing_001.py",
                "content": test_source,
            },
        }

    return author


def run_verify(tmp_path, test_source):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_author(test_source, log_path)
    )
    return report, log_path


def criterion_entry(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return matches[0]


def test_mutation_score_below_bar_fails_overall(tmp_path):
    report, log_path = run_verify(tmp_path, WEAK_TEST_SOURCE)

    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").count("called") >= 1

    entry = criterion_entry(report)
    assert field(entry, "kind") == "generated-test"
    # The mutation score changes only the overall verdict, never the criterion's result.
    assert field(entry, "result") == "pass"

    score = field(report, "mutation_score")
    assert score is not None
    assert isinstance(score, (int, float))
    # Three mutants (x * 2 -> x / 2, True -> False, == -> !=); only the first is killed.
    assert score < 0.8
    assert abs(score - (1.0 / 3.0)) < 1e-9
    assert field(report, "mutation_error") is None

    assert field(report, "overall") == "fail"

    as_dict = report.to_dict()
    assert as_dict["overall"] == "fail"
    assert as_dict["mutation_score"] < 0.8


def test_same_fixture_with_strong_suite_meets_bar(tmp_path):
    report, _ = run_verify(tmp_path, STRONG_TEST_SOURCE)

    entry = criterion_entry(report)
    assert field(entry, "result") == "pass"

    score = field(report, "mutation_score")
    assert score is not None
    assert score >= 0.8
    assert field(report, "mutation_error") is None
    assert field(report, "overall") == "pass"