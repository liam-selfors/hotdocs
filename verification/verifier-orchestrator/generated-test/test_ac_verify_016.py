# hotdocs-criterion: sha256:38afd8ec740f1485e11dcdc9867687e668c0c00fffd166e6b14c2b1f137f0d05
# Test for AC-VERIFY-016 (covers R-VERIFY-014):
# A mutant whose loop never terminates is killed by its per-mutant timeout,
# and verify returns within ten seconds.
import hashlib
import json
import threading
import time
from pathlib import Path

import verifier_orchestrator


SLUG = "loop-counter"
MODULE = "loop_counter"
COMPONENT_ID = "comp-loop-counter"
CRITERION_ID = "AC-LOOP-001"
REQUIREMENT_ID = "R-LOOP-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERION_TEXT = (
    "# AC-LOOP-001\n"
    "\n"
    "Covers: R-LOOP-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given a number is 3\n"
    "When count_up is invoked with 3\n"
    "Then result equals 3\n"
    "```\n"
)

REQUIREMENT_TEXT = (
    "# R-LOOP-001\n"
    "\n"
    "**R-LOOP-001** - `count_up(x)` MUST count from 0 up to `x` one step\n"
    "at a time and return the final count.\n"
)

INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "count_up(x: int) -> int\n"
    "```\n"
)

GLOSSARY_TEXT = "# Glossary\n\n- **Count** - a number reached by counting.\n"

MODULE_SOURCE = (
    "def count_up(x):\n"
    "    i = 0\n"
    "    while i < x:\n"
    "        i = i + 1\n"
    "    return i\n"
)


def bundle_dict():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
        "testing": "",
    }


def header_line(bundle):
    keys = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    payload = json.dumps(
        {k: bundle[k] for k in keys},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generated_test_source():
    return (
        header_line(bundle_dict()) + "\n"
        "import " + MODULE + "\n"
        "\n"
        "\n"
        "def test_count_up_reaches_three():\n"
        "    assert " + MODULE + ".count_up(3) == 3\n"
    )


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Loop counter\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-LOOP]\n"
        "---\n"
        "\n"
        "# Loop counter\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Counts up to a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: counting.\n"
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
        "- Initial draft.\n",
    )
    write(comp / "requirements" / (REQUIREMENT_ID + ".md"), REQUIREMENT_TEXT)
    write(comp / "acceptance" / (CRITERION_ID + ".md"), CRITERION_TEXT)
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "loop.md",
        "---\n"
        "id: P-LOOP\n"
        "title: Loop capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Loop capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Counting.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- Counting.\n"
        "\n"
        "### CS-LOOP-001\n"
        "\n"
        "Covers: P-LOOP\n"
        "\n"
        "```gherkin\n"
        "Given a number is 3\n"
        "When count_up is invoked with 3\n"
        "Then result equals 3\n"
        "```\n",
    )
    write(repo_root / "specs" / "glossary.md", GLOSSARY_TEXT)

    # The component's code: one short function with the loop under test.
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), MODULE_SOURCE)

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle_dict()) + "\n"
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


def make_author(log_path):
    content = generated_test_source()

    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/" + SLUG + "/generated-test/test_ac_loop_001.py",
                "content": content,
            },
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return author


def test_non_terminating_mutant_is_killed_within_ten_seconds(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"
    author = make_author(log_path)

    outcome = {}

    def run_verify():
        try:
            outcome["report"] = verifier_orchestrator.verify(
                COMPONENT_ID, repo_root, judge=None, test_author=author
            )
        except BaseException as exc:  # noqa: BLE001
            outcome["error"] = exc

    worker = threading.Thread(target=run_verify, daemon=True)
    start = time.monotonic()
    worker.start()
    worker.join(120)
    elapsed = time.monotonic() - start

    assert not worker.is_alive(), "verify did not return (still running after 120 seconds)"
    assert "error" not in outcome, "verify raised: " + repr(outcome.get("error"))
    report = outcome["report"]

    # It returns within ten seconds.
    assert elapsed < 10.0, "verify took " + repr(elapsed) + " seconds"

    # The generated test was authored by our stand-in and passed on unmutated code.
    assert log_path.read_text(encoding="utf-8").splitlines() == ["called"]
    criteria = field(report, "criteria")
    entries = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(entries) == 1
    assert field(entries[0], "result") == "pass"

    # The mutation run completed without error, and every mutant - including
    # `i = i - 1`, which never terminates - counts as killed.
    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None
    assert score == 1.0