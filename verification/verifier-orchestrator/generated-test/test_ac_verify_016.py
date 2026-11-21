# hotdocs-criterion: sha256:44a3f920e3dc0e7046e6b413cd1873448d4e290cc94a34d768058da7a4d99c41
import importlib.util
import sys
import threading
import time
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERION_TEXT = (
    "Given a loopy count is 3\n"
    "When count_up is invoked with 3\n"
    "Then the result equals 3\n"
)

REQUIREMENT_TEXT = (
    "**R-LOOPY-001** - `count_up(x)` MUST return `x` for a non-negative "
    "integer `x`, by counting up from zero.\n"
)

INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "count_up(x: int) -> int\n"
    "```\n"
)

GENERATED_TEST = (
    "import loopy\n"
    "\n"
    "\n"
    "def test_count_up_three():\n"
    "    assert loopy.count_up(3) == 3\n"
)

MODULE_SOURCE = (
    "def count_up(x):\n"
    "    i = 0\n"
    "    while i < x:\n"
    "        i = i + 1\n"
    "    return i\n"
)


def build_fixture(repo_root, log_dir):
    write(
        repo_root / "specs" / "product" / "loopy.md",
        "---\n"
        "id: P-LOOPY\n"
        "title: Loopy capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Loopy capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Counting up.\n",
    )
    comp = repo_root / "specs" / "components" / "loopy"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-loopy\n"
        "title: Loopy\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-LOOPY]\n"
        "---\n"
        "\n"
        "# Loopy\n"
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
        "- Initial.\n",
    )
    write(comp / "requirements" / "R-LOOPY-001.md", "# R-LOOPY-001\n\n" + REQUIREMENT_TEXT)
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-LOOPY-001.md",
        "# AC-LOOPY-001\n"
        "\n"
        "Covers: R-LOOPY-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n" + CRITERION_TEXT + "```\n",
    )

    write(repo_root / "gen" / "loopy" / "loopy.py", MODULE_SOURCE)

    bundle_literal = {
        "component_id": "comp-loopy",
        "criterion_id": "AC-LOOPY-001",
        "covers": "R-LOOPY-001",
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": "",
        "dependency_interfaces": {},
        "testing": "",
    }
    assembler_log = str(log_dir / "assembler.log")
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(" + repr(assembler_log) + ", 'a') as fh:\n"
        "        fh.write(str(criterion_id) + '\\n')\n"
        "    bundle = dict(" + repr(bundle_literal) + ")\n"
        "    bundle['component_id'] = component_id\n"
        "    bundle['criterion_id'] = criterion_id\n"
        "    return bundle\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    raise RuntimeError('assemble is not used by verify')\n",
    )

    probe_log = str(log_dir / "probe.log")
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
        "    with open(" + repr(probe_log) + ", 'a') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return ProbeReport()\n",
    )


def make_test_author(log_path):
    def test_author_stand_in(bundle):
        with open(log_path, "a") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/loopy/generated-test/test_ac_loopy_001.py",
                "content": GENERATED_TEST,
            },
        }

    return test_author_stand_in


def test_non_terminating_mutant_is_killed_within_ten_seconds(tmp_path):
    repo_root = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    repo_root.mkdir()
    log_dir.mkdir()
    build_fixture(repo_root, log_dir)
    author_log = log_dir / "author.log"
    author = make_test_author(str(author_log))

    outcome = {}

    def run():
        try:
            outcome["report"] = verifier_orchestrator.verify("comp-loopy", repo_root, test_author=author)
        except BaseException as exc:  # noqa: BLE001
            outcome["error"] = exc

    start = time.monotonic()
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(60)
    elapsed = time.monotonic() - start

    assert not worker.is_alive(), "verify did not return within 60 seconds"
    if "error" in outcome:
        raise outcome["error"]
    assert elapsed < 10.0, "verify took " + repr(elapsed) + " seconds"

    report = outcome["report"]

    # The test author was actually used for the criterion.
    assert author_log.is_file()
    assert author_log.read_text().count("called") >= 1

    criteria = field(report, "criteria")
    entry = next(c for c in criteria if field(c, "id") == "AC-LOOPY-001")
    assert field(entry, "result") == "pass"

    # Two mutants exist (`i < x` -> `i >= x`, and the non-terminating
    # `i + 1` -> `i - 1`); a score of 1.0 means the non-terminating one,
    # whose run times out, counts as killed.
    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") == 1.0